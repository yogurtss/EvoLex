from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from evolex.agents.deepseek_client import BaseExtractor, LLMConfig, get_default_extractor
from evolex.graph.state import GraphState
from evolex.nodes.candidate_store import make_candidate_store_node
from evolex.nodes.critic import critic_node
from evolex.nodes.entity_resolve import entity_resolve_node
from evolex.nodes.extract import make_extract_node
from evolex.nodes.ingest import ingest_node
from evolex.nodes.policy_node import policy_node
from evolex.nodes.profile import profile_node
from evolex.nodes.publish import make_publish_node
from evolex.nodes.quality_review import make_quality_review_node
from evolex.nodes.relation_extract import make_relation_extract_node
from evolex.nodes.schema_gap import schema_gap_node
from evolex.nodes.schema_proposer import schema_proposer_node
from evolex.nodes.segment import segment_node
from evolex.nodes.validate import validate_node

NodeCallback = Callable[[str], None]
GraphLogCallback = Callable[[str, str], None]
PipelineMode = Literal["phase1", "phase1+2", "phase3"]
NodeFunc = Callable[[GraphState], dict]


def _pipeline_nodes(
    extractor: BaseExtractor,
    output_dir: Path | None,
    pipeline: PipelineMode,
) -> list[tuple[str, NodeFunc]]:
    """Build the ordered list of (name, func) tuples for the given pipeline."""
    base: list[tuple[str, NodeFunc]] = [
        ("ingest", ingest_node),
        ("profile", profile_node),
        ("segment", segment_node),
        ("extract", make_extract_node(extractor)),
        ("validate", validate_node),
        ("candidate_store", make_candidate_store_node(output_dir)),
    ]

    if pipeline == "phase1":
        return base

    if pipeline == "phase1+2":
        base.extend(
            [
                ("entity_resolve", entity_resolve_node),
                ("relation_extract", make_relation_extract_node(extractor)),
                ("quality_review", make_quality_review_node()),
                ("publish", make_publish_node(output_dir)),
            ]
        )
        return base

    # pipeline == "phase3"
    base.extend(
        [
            ("entity_resolve", entity_resolve_node),
            ("relation_extract", make_relation_extract_node(extractor)),
            ("schema_gap", schema_gap_node),
            ("schema_proposer", schema_proposer_node),
            ("quality_review", make_quality_review_node()),
            ("critic", critic_node),
            ("policy", policy_node),
            ("quarantine", _quarantine_node),
            ("publish", make_publish_node(output_dir)),
        ]
    )
    return base


def _quarantine_node(state: GraphState) -> dict:
    """Quarantine handler: preserve the state with quarantine reason."""
    warnings: list[str] = list(state.get("warnings", []))
    policy_decisions = state.get("policy_decisions", [])
    if policy_decisions:
        reasons = policy_decisions[0].get("reasons", ["unknown"])
        warnings.append(f"quarantine: {', '.join(reasons)}")
    return {
        "status": "quarantined",
        "warnings": warnings,
    }


# -- routing helpers -----------------------------------------------------------


def route_after_validate(state: GraphState) -> str:
    """After validate: route to critic, quarantine, or reject."""
    status = state.get("status", "running")
    if status in ("failed", "quarantined"):
        return "quarantine"
    return "critic"


def route_after_policy(state: GraphState) -> str:
    """After policy: route to publish, candidate(END), quarantine, or reject."""
    decisions = state.get("policy_decisions", [])
    if not decisions:
        return "candidate"
    action = decisions[0].get("action", "candidate")
    if action == "publish":
        return "publish"
    if action == "quarantine":
        return "quarantine"
    if action == "reject":
        return "reject"
    return "candidate"


# -- graph runners -------------------------------------------------------------


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
        llm_config: LLMConfig | None = None,
    ) -> None:
        self.extractor = extractor or get_default_extractor(
            on_event=on_event,
            typed=(pipeline == "phase3"),
            llm_config=llm_config,
        )
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
        llm_config: LLMConfig | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1",
            on_event=on_event,
            llm_config=llm_config,
        )


class Phase2Graph(PipelineGraph):
    """Backward-compatible deterministic runner for the full Phase 1 + 2 topology."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
        llm_config: LLMConfig | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1+2",
            on_event=on_event,
            llm_config=llm_config,
        )


class Phase3Graph(PipelineGraph):
    """Deterministic runner with Phase 3 critic + policy nodes."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
        llm_config: LLMConfig | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase3",
            on_event=on_event,
            llm_config=llm_config,
        )


class LangGraphPipelineRunner:
    """Thin adapter around LangGraph StateGraph for the configured topology."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        pipeline: PipelineMode = "phase1",
        on_event: GraphLogCallback | None = None,
        llm_config: LLMConfig | None = None,
    ) -> None:
        from langgraph.graph import END, START, StateGraph

        extractor = extractor or get_default_extractor(
            on_event=on_event,
            typed=(pipeline == "phase3"),
            llm_config=llm_config,
        )
        graph = StateGraph(GraphState)
        nodes = _pipeline_nodes(extractor, output_dir, pipeline)
        for node_name, node_func in nodes:
            graph.add_node(node_name, node_func)

        if pipeline == "phase3":
            # Phase 3: linear up to quality_review, then conditional
            node_names = [n[0] for n in nodes]
            graph.add_edge(START, node_names[0])
            for i in range(0, node_names.index("quality_review")):
                graph.add_edge(node_names[i], node_names[i + 1])

            # Conditional after quality_review → critic or quarantine
            graph.add_conditional_edges(
                "quality_review",
                route_after_validate,
                {"critic": "critic", "quarantine": "quarantine"},
            )
            # critic → policy
            graph.add_edge("critic", "policy")
            # Conditional after policy
            graph.add_conditional_edges(
                "policy",
                route_after_policy,
                {
                    "publish": "publish",
                    "candidate": END,
                    "quarantine": "quarantine",
                    "reject": END,
                },
            )
            graph.add_edge("publish", END)
            graph.add_edge("quarantine", END)
        else:
            # Linear for phase1 and phase1+2
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
        llm_config: LLMConfig | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1",
            on_event=on_event,
            llm_config=llm_config,
        )


class LangGraphPhase2Runner(LangGraphPipelineRunner):
    """Backward-compatible LangGraph adapter for the full Phase 1 + 2 topology."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
        llm_config: LLMConfig | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1+2",
            on_event=on_event,
            llm_config=llm_config,
        )


# -- top-level factory ---------------------------------------------------------


def build_graph(
    extractor: BaseExtractor | None = None,
    output_dir: Path | None = None,
    pipeline: PipelineMode = "phase1",
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
) -> PipelineGraph | LangGraphPipelineRunner:
    try:
        import langgraph  # noqa: F401
    except ImportError:
        cls = {
            "phase1": Phase1Graph,
            "phase1+2": Phase2Graph,
            "phase3": Phase3Graph,
        }.get(pipeline, Phase1Graph)
        return cls(
            extractor=extractor,
            output_dir=output_dir,
            on_event=on_event,
            llm_config=llm_config,
        )

    return LangGraphPipelineRunner(
        extractor=extractor,
        output_dir=output_dir,
        pipeline=pipeline,
        on_event=on_event,
        llm_config=llm_config,
    )


def build_fallback_graph(
    extractor: BaseExtractor | None = None,
    output_dir: Path | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
) -> Phase1Graph:
    return Phase1Graph(
        extractor=extractor,
        output_dir=output_dir,
        on_event=on_event,
        llm_config=llm_config,
    )
