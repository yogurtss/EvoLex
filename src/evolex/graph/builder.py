from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from evolex.agents.deepseek_client import BaseExtractor, get_default_extractor
from evolex.graph.state import GraphState
from evolex.nodes.candidate_store import make_candidate_store_node
from evolex.nodes.entity_resolve import entity_resolve_node
from evolex.nodes.extract import make_extract_node
from evolex.nodes.ingest import ingest_node
from evolex.nodes.profile import profile_node
from evolex.nodes.publish import make_publish_node
from evolex.nodes.quality_review import make_quality_review_node
from evolex.nodes.relation_extract import make_relation_extract_node
from evolex.nodes.segment import segment_node
from evolex.nodes.validate import validate_node

NodeCallback = Callable[[str], None]
GraphLogCallback = Callable[[str, str], None]
PipelineMode = Literal["phase1", "phase1+2"]
NodeFunc = Callable[[GraphState], dict]


def _pipeline_nodes(
    extractor: BaseExtractor,
    output_dir: Path | None,
    pipeline: PipelineMode,
) -> list[tuple[str, NodeFunc]]:
    nodes: list[tuple[str, NodeFunc]] = [
        ("ingest", ingest_node),
        ("profile", profile_node),
        ("segment", segment_node),
        ("extract", make_extract_node(extractor)),
        ("validate", validate_node),
        ("candidate_store", make_candidate_store_node(output_dir)),
    ]

    if pipeline == "phase1+2":
        nodes.extend(
            [
                ("entity_resolve", entity_resolve_node),
                ("relation_extract", make_relation_extract_node(extractor)),
                ("quality_review", make_quality_review_node()),
                ("publish", make_publish_node(output_dir)),
            ]
        )

    return nodes


class PipelineGraph:
    """Small deterministic graph runner matching the configured topology.

    The node boundaries intentionally mirror the planned LangGraph graph, while
    keeping local smoke tests independent from optional runtime services.
    """

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        pipeline: PipelineMode = "phase1",
        on_event: GraphLogCallback | None = None,
    ) -> None:
        self.extractor = extractor or get_default_extractor(on_event=on_event)
        self.output_dir = output_dir
        self.pipeline = pipeline
        self.nodes = _pipeline_nodes(self.extractor, output_dir, pipeline)

    def invoke(
        self,
        initial_state: GraphState,
        on_node: NodeCallback | None = None,
    ) -> GraphState:
        state: GraphState = dict(initial_state)
        for node_name, node_func in self.nodes:
            update = node_func(state)
            state.update(update)
            if on_node is not None:
                on_node(node_name)
        return state


class Phase1Graph(PipelineGraph):
    """Backward-compatible deterministic runner for the Phase 1 topology."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1",
            on_event=on_event,
        )


class Phase2Graph(PipelineGraph):
    """Backward-compatible deterministic runner for the full Phase 1 + 2 topology."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1+2",
            on_event=on_event,
        )


class LangGraphPipelineRunner:
    """Thin adapter around LangGraph StateGraph for the configured topology."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        pipeline: PipelineMode = "phase1",
        on_event: GraphLogCallback | None = None,
    ) -> None:
        from langgraph.graph import END, START, StateGraph

        extractor = extractor or get_default_extractor(on_event=on_event)
        graph = StateGraph(GraphState)
        nodes = _pipeline_nodes(extractor, output_dir, pipeline)
        for node_name, node_func in nodes:
            graph.add_node(node_name, node_func)

        graph.add_edge(START, nodes[0][0])
        for from_node, to_node in zip(nodes, nodes[1:], strict=False):
            graph.add_edge(from_node[0], to_node[0])
        graph.add_edge(nodes[-1][0], END)

        self.compiled = graph.compile()

    def invoke(
        self,
        initial_state: GraphState,
        on_node: NodeCallback | None = None,
    ) -> GraphState:
        if on_node is None:
            return self.compiled.invoke(initial_state)

        state: GraphState = dict(initial_state)
        for update in self.compiled.stream(initial_state, stream_mode="updates"):
            for node_name, node_update in update.items():
                if isinstance(node_update, dict):
                    state.update(node_update)
                on_node(node_name)
        return state


class LangGraphPhase1Runner(LangGraphPipelineRunner):
    """Backward-compatible LangGraph adapter for the Phase 1 topology."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1",
            on_event=on_event,
        )


class LangGraphPhase2Runner(LangGraphPipelineRunner):
    """Backward-compatible LangGraph adapter for the full Phase 1 + 2 topology."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1+2",
            on_event=on_event,
        )


def build_graph(
    extractor: BaseExtractor | None = None,
    output_dir: Path | None = None,
    pipeline: PipelineMode = "phase1",
    on_event: GraphLogCallback | None = None,
) -> PipelineGraph | LangGraphPipelineRunner:
    try:
        import langgraph  # noqa: F401
    except ImportError:
        return PipelineGraph(
            extractor=extractor,
            output_dir=output_dir,
            pipeline=pipeline,
            on_event=on_event,
        )

    return LangGraphPipelineRunner(
        extractor=extractor,
        output_dir=output_dir,
        pipeline=pipeline,
        on_event=on_event,
    )


def build_fallback_graph(
    extractor: BaseExtractor | None = None,
    output_dir: Path | None = None,
    on_event: GraphLogCallback | None = None,
) -> Phase1Graph:
    return Phase1Graph(extractor=extractor, output_dir=output_dir, on_event=on_event)
