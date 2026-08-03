from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Literal

from evolex.agents.deepseek_client import BaseExtractor, LLMConfig, get_default_extractor
from evolex.graph.state import GraphState
from evolex.nodes.candidate_store import make_candidate_store_node
from evolex.nodes.critic import critic_node
from evolex.nodes.entity_merge import entity_merge_node
from evolex.nodes.entity_resolve import entity_resolve_node
from evolex.nodes.extract import make_extract_node
from evolex.nodes.ingest import ingest_node
from evolex.nodes.policy_node import policy_node
from evolex.nodes.profile import profile_node
from evolex.nodes.publish import make_publish_node
from evolex.nodes.quality_review import make_quality_review_node
from evolex.nodes.relation_extract import make_relation_extract_node
from evolex.nodes.relation_merge import relation_merge_node
from evolex.nodes.registry_finalize import make_registry_finalize_node
from evolex.nodes.schema_gap import make_schema_gap_node
from evolex.nodes.schema_proposer import schema_proposer_node
from evolex.nodes.segment import segment_node
from evolex.nodes.validate import validate_node
from evolex.repositories.evaluation import CheckpointStore

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
    schema_dir = (output_dir / "schema_candidates") if output_dir else None
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
                ("entity_merge", entity_merge_node),
                ("relation_extract", make_relation_extract_node(extractor)),
                ("relation_merge", relation_merge_node),
                ("quality_review", make_quality_review_node()),
                ("publish", make_publish_node(output_dir)),
            ]
        )
        return base

    # pipeline == "phase3"
    base.extend(
        [
            ("entity_resolve", entity_resolve_node),
            ("entity_merge", entity_merge_node),
            ("relation_extract", make_relation_extract_node(extractor)),
            ("relation_merge", relation_merge_node),
            ("schema_gap", make_schema_gap_node(schema_dir)),
            ("schema_proposer", schema_proposer_node),
            ("quality_review", make_quality_review_node()),
            ("critic", critic_node),
            ("policy", policy_node),
            ("quarantine", _quarantine_node),
            ("publish", make_publish_node(output_dir)),
            ("registry_finalize", make_registry_finalize_node(output_dir)),
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


def _append_audit_event(
    state: GraphState,
    *,
    node_name: str,
    status_before: str | None,
    status_after: str | None,
    warnings_before: list[str],
    elapsed_seconds: float | None = None,
) -> None:
    warnings_after = list(state.get("warnings", []))
    new_warnings = warnings_after[len(warnings_before):]
    decision = None
    if node_name == "policy" and state.get("policy_decisions"):
        decision = state["policy_decisions"][0].get("action")
    event = {
        "node_name": node_name,
        "status_before": status_before,
        "status_after": status_after,
        "decision": decision,
        "warnings": ", ".join(str(w) for w in new_warnings),
        "elapsed_seconds": elapsed_seconds,
    }
    state.setdefault("audit_events", []).append(event)


def _with_audit(
    node_name: str,
    node_func: NodeFunc,
    checkpoint_store: CheckpointStore | None = None,
) -> NodeFunc:
    def wrapped(state: GraphState) -> dict:
        next_state: GraphState = dict(state)
        status_before = next_state.get("status")
        warnings_before = list(next_state.get("warnings", []))
        start = perf_counter()
        update = node_func(state)
        elapsed = perf_counter() - start
        next_state.update(update)
        _append_audit_event(
            next_state,
            node_name=node_name,
            status_before=status_before,
            status_after=next_state.get("status"),
            warnings_before=warnings_before,
            elapsed_seconds=elapsed,
        )
        update["audit_events"] = next_state.get("audit_events", [])
        if checkpoint_store is not None:
            next_state["checkpoint_path"] = str(checkpoint_store.db_path)
            update["checkpoint_path"] = str(checkpoint_store.db_path)
            checkpoint_store.put_checkpoint(
                next_state,
                node_name=node_name,
                step_index=len(next_state.get("audit_events", [])),
            )
        return update

    return wrapped


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
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        self.extractor = extractor or get_default_extractor(
            on_event=on_event,
            typed=(pipeline == "phase3"),
            llm_config=llm_config,
        )
        self.output_dir = output_dir
        self.pipeline = pipeline
        self.checkpoint_store = checkpoint_store
        self._step_index = 0
        self.nodes = _pipeline_nodes(self.extractor, output_dir, pipeline)
        self.node_map = dict(self.nodes)

    def invoke(
        self,
        initial_state: GraphState,
        on_node: NodeCallback | None = None,
    ) -> GraphState:
        state: GraphState = dict(initial_state)
        if self.pipeline == "phase3":
            return self._invoke_phase3(state, on_node=on_node)
        for node_name, node_func in self.nodes:
            self._run_node(state, node_name, node_func)
            if on_node is not None:
                on_node(node_name)
        return state

    def _invoke_phase3(
        self,
        state: GraphState,
        on_node: NodeCallback | None = None,
    ) -> GraphState:
        for node_name, node_func in self.nodes:
            if node_name in {"quarantine", "publish", "registry_finalize"}:
                continue
            self._run_node(state, node_name, node_func)
            if on_node is not None:
                on_node(node_name)
            if node_name == "quality_review" and route_after_validate(state) == "quarantine":
                self._run_node(state, "quarantine", self.node_map["quarantine"])
                if on_node is not None:
                    on_node("quarantine")
                break
            if node_name == "policy":
                action = route_after_policy(state)
                if action == "publish":
                    self._run_node(state, "publish", self.node_map["publish"])
                    if on_node is not None:
                        on_node("publish")
                elif action == "quarantine":
                    self._run_node(state, "quarantine", self.node_map["quarantine"])
                    if on_node is not None:
                        on_node("quarantine")
                break
        self._run_node(state, "registry_finalize", self.node_map["registry_finalize"])
        if on_node is not None:
            on_node("registry_finalize")
        return state

    def _run_node(self, state: GraphState, node_name: str, node_func: NodeFunc) -> None:
        status_before = state.get("status")
        warnings_before = list(state.get("warnings", []))
        start = perf_counter()
        update = node_func(state)
        elapsed = perf_counter() - start
        state.update(update)
        _append_audit_event(
            state,
            node_name=node_name,
            status_before=status_before,
            status_after=state.get("status"),
            warnings_before=warnings_before,
            elapsed_seconds=elapsed,
        )
        self._step_index += 1
        self._save_checkpoint(state, node_name)

    def _save_checkpoint(self, state: GraphState, node_name: str) -> None:
        if self.checkpoint_store is None:
            return
        state["checkpoint_path"] = str(self.checkpoint_store.db_path)
        self.checkpoint_store.put_checkpoint(
            state,
            node_name=node_name,
            step_index=self._step_index,
        )

    def resume_from_checkpoint(
        self,
        checkpoint: dict,
        on_node: NodeCallback | None = None,
    ) -> GraphState:
        """Continue this deterministic runner after a stored checkpoint."""
        state: GraphState = dict(checkpoint["state"])
        node_names = [name for name, _ in self.nodes]
        completed = checkpoint.get("node_name", "")
        start_index = node_names.index(completed) + 1 if completed in node_names else 0
        self._step_index = int(checkpoint.get("step_index", start_index))

        if self.pipeline == "phase3":
            # A checkpoint records a completed node, but a branch decision is
            # made immediately after that node.  On resume, consume that
            # already-produced output before walking the remaining linear tail.
            if (
                completed == "quality_review"
                and route_after_validate(state) == "quarantine"
            ):
                self._run_node(state, "quarantine", self.node_map["quarantine"])
                if on_node is not None:
                    on_node("quarantine")
                self._run_node(
                    state,
                    "registry_finalize",
                    self.node_map["registry_finalize"],
                )
                if on_node is not None:
                    on_node("registry_finalize")
                return state

            if completed == "policy":
                action = route_after_policy(state)
                if action == "publish":
                    self._run_node(state, "publish", self.node_map["publish"])
                    if on_node is not None:
                        on_node("publish")
                elif action == "quarantine":
                    self._run_node(
                        state,
                        "quarantine",
                        self.node_map["quarantine"],
                    )
                    if on_node is not None:
                        on_node("quarantine")
                self._run_node(
                    state,
                    "registry_finalize",
                    self.node_map["registry_finalize"],
                )
                if on_node is not None:
                    on_node("registry_finalize")
                return state

            tail = [(name, fn) for name, fn in self.nodes[start_index:]]
            for node_name, node_func in tail:
                if node_name in {"quarantine", "publish", "registry_finalize"}:
                    continue
                self._run_node(state, node_name, node_func)
                if on_node is not None:
                    on_node(node_name)
                if node_name == "quality_review" and route_after_validate(state) == "quarantine":
                    self._run_node(state, "quarantine", self.node_map["quarantine"])
                    if on_node is not None:
                        on_node("quarantine")
                    break
                if node_name == "policy":
                    action = route_after_policy(state)
                    if action == "publish":
                        self._run_node(state, "publish", self.node_map["publish"])
                        if on_node is not None:
                            on_node("publish")
                    elif action == "quarantine":
                        self._run_node(state, "quarantine", self.node_map["quarantine"])
                        if on_node is not None:
                            on_node("quarantine")
                    break
            if start_index <= node_names.index("registry_finalize"):
                self._run_node(state, "registry_finalize", self.node_map["registry_finalize"])
                if on_node is not None:
                    on_node("registry_finalize")
            return state

        for node_name, node_func in self.nodes[start_index:]:
            self._run_node(state, node_name, node_func)
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
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1",
            on_event=on_event,
            llm_config=llm_config,
            checkpoint_store=checkpoint_store,
        )


class Phase2Graph(PipelineGraph):
    """Backward-compatible deterministic runner for the full Phase 1 + 2 topology."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
        llm_config: LLMConfig | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1+2",
            on_event=on_event,
            llm_config=llm_config,
            checkpoint_store=checkpoint_store,
        )


class Phase3Graph(PipelineGraph):
    """Deterministic runner with Phase 3 critic + policy nodes."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
        llm_config: LLMConfig | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase3",
            on_event=on_event,
            llm_config=llm_config,
            checkpoint_store=checkpoint_store,
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
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        from langgraph.graph import END, START, StateGraph

        extractor = extractor or get_default_extractor(
            on_event=on_event,
            typed=(pipeline == "phase3"),
            llm_config=llm_config,
        )
        self.extractor = extractor
        graph = StateGraph(GraphState)
        nodes = _pipeline_nodes(extractor, output_dir, pipeline)
        for node_name, node_func in nodes:
            graph.add_node(node_name, _with_audit(node_name, node_func, checkpoint_store))

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
                    "candidate": "registry_finalize",
                    "quarantine": "quarantine",
                    "reject": "registry_finalize",
                },
            )
            graph.add_edge("publish", "registry_finalize")
            graph.add_edge("quarantine", "registry_finalize")
            graph.add_edge("registry_finalize", END)
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
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1",
            on_event=on_event,
            llm_config=llm_config,
            checkpoint_store=checkpoint_store,
        )


class LangGraphPhase2Runner(LangGraphPipelineRunner):
    """Backward-compatible LangGraph adapter for the full Phase 1 + 2 topology."""

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
        llm_config: LLMConfig | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        super().__init__(
            extractor=extractor,
            output_dir=output_dir,
            pipeline="phase1+2",
            on_event=on_event,
            llm_config=llm_config,
            checkpoint_store=checkpoint_store,
        )


# -- top-level factory ---------------------------------------------------------


def build_graph(
    extractor: BaseExtractor | None = None,
    output_dir: Path | None = None,
    pipeline: PipelineMode = "phase1",
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
    checkpoint_store: CheckpointStore | None = None,
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
            checkpoint_store=checkpoint_store,
        )

    return LangGraphPipelineRunner(
        extractor=extractor,
        output_dir=output_dir,
        pipeline=pipeline,
        on_event=on_event,
        llm_config=llm_config,
        checkpoint_store=checkpoint_store,
    )


def build_fallback_graph(
    extractor: BaseExtractor | None = None,
    output_dir: Path | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
    checkpoint_store: CheckpointStore | None = None,
) -> Phase1Graph:
    return Phase1Graph(
        extractor=extractor,
        output_dir=output_dir,
        on_event=on_event,
        llm_config=llm_config,
        checkpoint_store=checkpoint_store,
    )
