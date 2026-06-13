from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from evolex.agents.deepseek_client import BaseExtractor, LLMConfig
from evolex.graph.builder import GraphLogCallback, PipelineMode, build_graph
from evolex.graph.state import GraphState


@dataclass(frozen=True)
class Phase1RunResult:
    run_id: str
    document_id: str
    status: str
    segment_count: int
    semantic_atom_count: int
    candidate_output_path: str
    state: GraphState


PipelineAlias = Literal["phase1", "phase1+2", "phase2", "phase3", "full", "system"]


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


def run_system_text(
    document_text: str,
    document_version: int = 1,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
) -> SystemRunResult:
    return run_phase3_text(
        document_text=document_text,
        document_version=document_version,
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
        llm_config=llm_config,
    )


def run_system_file(
    path: Path,
    document_version: int = 1,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
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
    )


def run_phase3_text(
    document_text: str,
    document_version: int = 1,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
    llm_config: LLMConfig | None = None,
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
) -> Phase1RunResult | Phase2RunResult | Phase3RunResult:
    pipeline_mode = normalize_pipeline(pipeline)
    run_id = f"RUN-{uuid4().hex[:12]}"
    document_id = f"DOC-{uuid4().hex[:12]}"
    graph = build_graph(
        extractor=extractor,
        output_dir=output_dir,
        pipeline=pipeline_mode,
        on_event=on_event,
        llm_config=llm_config,
    )
    state = graph.invoke(
        {
            "run_id": run_id,
            "thread_id": f"document:{document_id}:{_thread_version(pipeline_mode)}",
            "document_id": document_id,
            "document_version": document_version,
            "document_text": document_text,
            "schema_version": "semiconductor-0.1.0",
            "policy_version": "policy-0.1.0",
            "graph_version": "graph-0.1.0",
            "prompt_versions": {},
            "model_routes": {},
            "llm_call_count": 0,
            "tool_call_count": 0,
            "retry_count": 0,
            "status": "running",
        },
        on_node=on_node,
    )
    if pipeline_mode == "phase3":
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
    )


# -- helpers ------------------------------------------------------------------


def normalize_pipeline(pipeline: PipelineAlias | str) -> PipelineMode:
    normalized = pipeline.lower().replace("_", "-").replace(" ", "")
    if normalized in ("system", "phase3", "p3", "full"):
        return "phase3"
    if normalized in ("phase1", "p1"):
        return "phase1"
    if normalized in ("phase1+2", "phase2", "p2"):
        return "phase1+2"
    msg = "pipeline must be one of: system, phase3, full, phase2, phase1"
    raise ValueError(msg)


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
