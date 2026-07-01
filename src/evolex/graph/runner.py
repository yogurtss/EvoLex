from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from evolex.agentic.controller import AgenticKGRunner
from evolex.agents.deepseek_client import BaseExtractor, HeuristicTypedExtractor, LLMConfig
from evolex.graph.builder import GraphLogCallback, PipelineGraph, PipelineMode, build_graph
from evolex.graph.state import GraphState
from evolex.repositories.candidates import CandidateRegistry
from evolex.repositories.evaluation import (
    CheckpointStore,
    FrozenCorpusStore,
    ShadowReportStore,
    diff_metrics,
    governance_snapshot,
    summarize_state,
)
from evolex.repositories.schema_store import SchemaCandidateStore


@dataclass(frozen=True)
class Phase1RunResult:
    run_id: str
    document_id: str
    status: str
    segment_count: int
    semantic_atom_count: int
    candidate_output_path: str
    state: GraphState


PipelineAlias = Literal[
    "phase1",
    "phase1+2",
    "phase2",
    "phase3",
    "full",
    "system",
    "agent",
    "agentic",
]


def run_phase1_text(
    document_text: str,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
) -> Phase1RunResult:
    result = run_pipeline_text(
        document_text=document_text,
        pipeline="phase1",
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
        llm_config=llm_config,
    )
    assert isinstance(result, Phase1RunResult)
    return result


def run_phase1_file(
    path: Path,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
) -> Phase1RunResult:
    result = run_pipeline_file(
        path=path,
        pipeline="phase1",
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
        llm_config=llm_config,
    )
    assert isinstance(result, Phase1RunResult)
    return result


# -- Phase II runners ---------------------------------------------------------


@dataclass(frozen=True)
class Phase2RunResult:
    run_id: str
    document_id: str
    status: str
    segment_count: int
    semantic_atom_count: int
    entity_count: int
    relation_count: int
    candidate_output_path: str
    publish_output_path: str
    state: GraphState


@dataclass(frozen=True)
class Phase3RunResult:
    run_id: str
    document_id: str
    document_version: int
    status: str
    segment_count: int
    semantic_atom_count: int
    entity_count: int
    relation_count: int
    claim_count: int
    evidence_count: int
    policy_action: str
    candidate_output_path: str
    publish_output_path: str
    state: GraphState


SystemRunResult = Phase3RunResult


@dataclass(frozen=True)
class FrozenEvaluationResult:
    status: str
    document_count: int
    report_path: str
    baseline_path: str
    report: dict


@dataclass(frozen=True)
class ShadowEvaluationResult:
    status: str
    document_count: int
    report_path: str
    report: dict


@dataclass(frozen=True)
class ReplayResult:
    run_id: str
    event_count: int
    events: list[dict]


@dataclass(frozen=True)
class ResumeResult:
    thread_id: str
    resumed_from_node: str
    result: Phase1RunResult | Phase2RunResult | Phase3RunResult


def run_system_text(
    document_text: str,
    document_version: int = 1,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
    checkpoint_dir: Path | None = None,
    evaluation_mode: str | None = None,
    baseline_run_id: str | None = None,
) -> SystemRunResult:
    return run_phase3_text(
        document_text=document_text,
        document_version=document_version,
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
        llm_config=llm_config,
        checkpoint_dir=checkpoint_dir,
        evaluation_mode=evaluation_mode,
        baseline_run_id=baseline_run_id,
    )


def run_system_file(
    path: Path,
    document_version: int = 1,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
    checkpoint_dir: Path | None = None,
    evaluation_mode: str | None = None,
    baseline_run_id: str | None = None,
) -> SystemRunResult:
    document_text = path.read_text(encoding="utf-8")
    return run_system_text(
        document_text=document_text,
        document_version=document_version,
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
        llm_config=llm_config,
        checkpoint_dir=checkpoint_dir,
        evaluation_mode=evaluation_mode,
        baseline_run_id=baseline_run_id,
    )


def run_phase3_text(
    document_text: str,
    document_version: int = 1,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
    checkpoint_dir: Path | None = None,
    evaluation_mode: str | None = None,
    baseline_run_id: str | None = None,
) -> Phase3RunResult:
    result = run_pipeline_text(
        document_text=document_text,
        pipeline="phase3",
        document_version=document_version,
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
        llm_config=llm_config,
        checkpoint_dir=checkpoint_dir,
        evaluation_mode=evaluation_mode,
        baseline_run_id=baseline_run_id,
    )
    assert isinstance(result, Phase3RunResult)
    return result


def run_phase2_text(
    document_text: str,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
) -> Phase2RunResult:
    result = run_pipeline_text(
        document_text=document_text,
        pipeline="phase1+2",
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
        llm_config=llm_config,
    )
    assert isinstance(result, Phase2RunResult)
    return result


def run_phase2_file(
    path: Path,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
) -> Phase2RunResult:
    result = run_pipeline_file(
        path=path,
        pipeline="phase1+2",
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
        llm_config=llm_config,
    )
    assert isinstance(result, Phase2RunResult)
    return result


def run_pipeline_text(
    document_text: str,
    pipeline: PipelineAlias = "system",
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    document_version: int = 1,
    llm_config: LLMConfig | None = None,
    checkpoint_dir: Path | None = None,
    evaluation_mode: str | None = None,
    baseline_run_id: str | None = None,
) -> Phase1RunResult | Phase2RunResult | Phase3RunResult:
    agentic_mode = is_agentic_pipeline(pipeline)
    pipeline_mode = "phase3" if agentic_mode else normalize_pipeline(pipeline)
    run_id = f"RUN-{uuid4().hex[:12]}"
    document_id = f"DOC-{uuid4().hex[:12]}"
    checkpoint_store = CheckpointStore(checkpoint_dir) if checkpoint_dir else None
    if agentic_mode:
        graph = AgenticKGRunner(
            extractor=extractor,
            output_dir=output_dir,
            on_event=on_event,
            llm_config=llm_config,
            checkpoint_store=checkpoint_store,
        )
    else:
        graph = build_graph(
            extractor=extractor,
            output_dir=output_dir,
            pipeline=pipeline_mode,
            on_event=on_event,
            llm_config=llm_config,
            checkpoint_store=checkpoint_store,
        )
    initial_state: GraphState = {
        "run_id": run_id,
        "thread_id": f"document:{document_id}:{'agent' if agentic_mode else _thread_version(pipeline_mode)}",
        "document_id": document_id,
        "document_version": document_version,
        "document_text": document_text,
        "schema_version": "semiconductor-0.1.0",
        "policy_version": "policy-0.1.0",
        "graph_version": "agentic-0.1.0" if agentic_mode else "graph-0.1.0",
        "prompt_versions": {},
        "model_routes": {},
        "llm_call_count": 0,
        "tool_call_count": 0,
        "retry_count": 0,
        "status": "running",
    }
    if evaluation_mode:
        initial_state["evaluation_mode"] = evaluation_mode
    if baseline_run_id:
        initial_state["baseline_run_id"] = baseline_run_id
    if checkpoint_store is not None:
        initial_state["checkpoint_path"] = str(checkpoint_store.db_path)
    state = graph.invoke(initial_state, on_node=on_node)
    if agentic_mode or pipeline_mode == "phase3":
        return _to_phase3_result(state)
    if pipeline_mode == "phase1+2":
        return _to_phase2_result(state)
    return _to_result(state)


def run_pipeline_file(
    path: Path,
    pipeline: PipelineAlias = "system",
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
    document_version: int = 1,
    checkpoint_dir: Path | None = None,
    evaluation_mode: str | None = None,
    baseline_run_id: str | None = None,
) -> Phase1RunResult | Phase2RunResult | Phase3RunResult:
    document_text = path.read_text(encoding="utf-8")
    return run_pipeline_text(
        document_text=document_text,
        pipeline=pipeline,
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
        llm_config=llm_config,
        document_version=document_version,
        checkpoint_dir=checkpoint_dir,
        evaluation_mode=evaluation_mode,
        baseline_run_id=baseline_run_id,
    )


def run_frozen_evaluation(
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    update_baseline: bool = False,
    project_root: Path | None = None,
) -> FrozenEvaluationResult:
    eval_dir = (output_dir / "eval") if output_dir else Path("data/eval")
    frozen_store = FrozenCorpusStore(eval_dir)
    docs = frozen_store.load_documents(project_root=project_root)
    run_dir = eval_dir / "frozen_runs"
    checkpoint_dir = eval_dir / "checkpoints"
    extractor = extractor or HeuristicTypedExtractor()

    document_reports: list[dict] = []
    totals = _empty_metrics()
    for document in docs:
        result = run_system_text(
            document.text,
            output_dir=run_dir,
            extractor=extractor,
            checkpoint_dir=checkpoint_dir,
            evaluation_mode="frozen",
        )
        metrics = summarize_state(result.state)
        metrics["frozen_document_id"] = document.document_id
        metrics["source_path"] = str(document.path)
        document_reports.append(metrics)
        _add_metrics(totals, metrics)

    report = {
        "status": "ok",
        "evaluation_mode": "frozen",
        "document_count": len(docs),
        "documents": document_reports,
        "totals": totals,
        "created_at": _now(),
    }
    baseline = frozen_store.load_baseline()
    report["diff"] = diff_metrics(baseline.get("totals") if baseline else None, totals)
    if update_baseline or baseline is None:
        frozen_store.save_baseline(report)
        report["baseline_updated"] = True
    else:
        report["baseline_updated"] = False
    report_path = frozen_store.save_report(report)
    return FrozenEvaluationResult(
        status="ok",
        document_count=len(docs),
        report_path=str(report_path),
        baseline_path=str(frozen_store.baseline_path),
        report=report,
    )


def run_shadow_evaluation(
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    project_root: Path | None = None,
) -> ShadowEvaluationResult:
    eval_dir = (output_dir / "eval") if output_dir else Path("data/eval")
    frozen_store = FrozenCorpusStore(eval_dir)
    report_store = ShadowReportStore(eval_dir)
    docs = frozen_store.load_documents(project_root=project_root)
    checkpoint_dir = eval_dir / "checkpoints"
    shadow_run_dir = eval_dir / "shadow_runs"
    extractor = extractor or HeuristicTypedExtractor()

    comparisons: list[dict] = []
    baseline_totals = _empty_metrics()
    shadow_totals = _empty_metrics()
    shadow_run_id = ""
    for document in docs:
        baseline = run_system_text(
            document.text,
            output_dir=shadow_run_dir,
            extractor=extractor,
            checkpoint_dir=checkpoint_dir,
            evaluation_mode="shadow",
        )
        shadow = run_system_text(
            document.text,
            output_dir=shadow_run_dir,
            extractor=extractor,
            checkpoint_dir=checkpoint_dir,
            evaluation_mode="shadow",
            baseline_run_id=baseline.run_id,
        )
        shadow_run_id = shadow.run_id
        baseline_metrics = summarize_state(baseline.state)
        shadow_metrics = summarize_state(shadow.state)
        _add_metrics(baseline_totals, baseline_metrics)
        _add_metrics(shadow_totals, shadow_metrics)
        comparisons.append(
            {
                "frozen_document_id": document.document_id,
                "source_path": str(document.path),
                "baseline": baseline_metrics,
                "shadow": shadow_metrics,
                "diff": diff_metrics(baseline_metrics, shadow_metrics),
            }
        )

    registry = CandidateRegistry(shadow_run_dir / "registry")
    schema_store = SchemaCandidateStore(shadow_run_dir / "schema_candidates")
    report = {
        "status": "ok",
        "evaluation_mode": "shadow",
        "shadow_run_id": shadow_run_id,
        "document_count": len(docs),
        "comparisons": comparisons,
        "totals": {
            "baseline": baseline_totals,
            "shadow": shadow_totals,
            "diff": diff_metrics(baseline_totals, shadow_totals),
        },
        "governance": governance_snapshot(
            schema_proposals=schema_store.get_proposals(limit=100),
            policy_decisions=registry.get_recent_policy_decisions(limit=100),
        ),
        "created_at": _now(),
    }
    report_path = report_store.save_report(report)
    report["report_path"] = str(report_path)
    return ShadowEvaluationResult(
        status="ok",
        document_count=len(docs),
        report_path=str(report_path),
        report=report,
    )


def replay_run(
    run_id: str,
    checkpoint_dir: Path | None = None,
) -> ReplayResult:
    store = CheckpointStore(checkpoint_dir)
    events = store.replay_run(run_id)
    return ReplayResult(run_id=run_id, event_count=len(events), events=events)


def resume_thread(
    thread_id: str,
    output_dir: Path | None = None,
    checkpoint_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    pipeline: PipelineAlias = "system",
    on_node: Callable[[str], None] | None = None,
    llm_config: LLMConfig | None = None,
) -> ResumeResult:
    pipeline_mode = normalize_pipeline(pipeline)
    store = CheckpointStore(checkpoint_dir)
    checkpoint = store.latest_for_thread(thread_id)
    if checkpoint is None:
        raise ValueError(f"no checkpoint found for thread_id: {thread_id}")
    graph = PipelineGraph(
        extractor=extractor or HeuristicTypedExtractor(),
        output_dir=output_dir,
        pipeline=pipeline_mode,
        llm_config=llm_config,
        checkpoint_store=store,
    )
    state = graph.resume_from_checkpoint(checkpoint, on_node=on_node)
    if pipeline_mode == "phase3":
        result = _to_phase3_result(state)
    elif pipeline_mode == "phase1+2":
        result = _to_phase2_result(state)
    else:
        result = _to_result(state)
    return ResumeResult(
        thread_id=thread_id,
        resumed_from_node=checkpoint["node_name"],
        result=result,
    )


# -- helpers ------------------------------------------------------------------


def normalize_pipeline(pipeline: PipelineAlias | str) -> PipelineMode:
    normalized = pipeline.lower().replace("_", "-").replace(" ", "")
    if normalized in ("agent", "agentic", "multiagent", "multi-agent"):
        return "phase3"
    if normalized in ("system", "phase3", "p3", "full"):
        return "phase3"
    if normalized in ("phase1", "p1"):
        return "phase1"
    if normalized in ("phase1+2", "phase2", "p2"):
        return "phase1+2"
    msg = "pipeline must be one of: system, phase3, full, phase2, phase1"
    raise ValueError(msg)


def is_agentic_pipeline(pipeline: PipelineAlias | str) -> bool:
    normalized = pipeline.lower().replace("_", "-").replace(" ", "")
    return normalized in ("agent", "agentic", "multiagent", "multi-agent")


def _thread_version(pipeline: PipelineMode) -> str:
    if pipeline == "phase3":
        return "v3"
    return "v2" if pipeline == "phase1+2" else "v1"


def _to_result(state: GraphState) -> Phase1RunResult:
    return Phase1RunResult(
        run_id=state["run_id"],
        document_id=state["document_id"],
        status=state["status"],
        segment_count=len(state.get("segments", [])),
        semantic_atom_count=len(state.get("semantic_atoms", [])),
        candidate_output_path=state.get("candidate_output_path", ""),
        state=state,
    )


def _to_phase2_result(state: GraphState) -> Phase2RunResult:
    return Phase2RunResult(
        run_id=state["run_id"],
        document_id=state["document_id"],
        status=state["status"],
        segment_count=len(state.get("segments", [])),
        semantic_atom_count=len(state.get("semantic_atoms", [])),
        entity_count=len(state.get("entities", [])),
        relation_count=len(state.get("relations", [])),
        candidate_output_path=state.get("candidate_output_path", ""),
        publish_output_path=state.get("publish_output_path", ""),
        state=state,
    )


def _to_phase3_result(state: GraphState) -> Phase3RunResult:
    policy_decisions = state.get("policy_decisions", [])
    policy_action = policy_decisions[0].get("action", "unknown") if policy_decisions else "unknown"
    return Phase3RunResult(
        run_id=state["run_id"],
        document_id=state["document_id"],
        document_version=state.get("document_version", 0),
        status=state["status"],
        segment_count=len(state.get("segments", [])),
        semantic_atom_count=len(state.get("semantic_atoms", [])),
        entity_count=len(state.get("entities", [])),
        relation_count=len(state.get("relations", [])),
        claim_count=len(state.get("claim_candidates", [])),
        evidence_count=len(state.get("evidence_spans", [])),
        policy_action=policy_action,
        candidate_output_path=state.get("candidate_output_path", ""),
        publish_output_path=state.get("publish_output_path", ""),
        state=state,
    )


def _empty_metrics() -> dict[str, int | float]:
    return {
        "claims": 0,
        "evidence": 0,
        "evidence_coverage": 0.0,
        "entities": 0,
        "relations": 0,
        "unsupported": 0,
        "ambiguous": 0,
        "entity_remaps": 0,
    }


def _add_metrics(total: dict[str, int | float], metrics: dict) -> None:
    claim_count_before = int(total.get("claims", 0))
    evidence_count_before = int(total.get("evidence", 0))
    for key in ("claims", "evidence", "entities", "relations", "unsupported", "ambiguous", "entity_remaps"):
        total[key] = int(total.get(key, 0)) + int(metrics.get(key, 0))
    claims = int(total.get("claims", 0))
    evidence = int(total.get("evidence", 0))
    if claims:
        total["evidence_coverage"] = round(evidence / claims, 3)
    elif claim_count_before or evidence_count_before:
        total["evidence_coverage"] = 0.0


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
