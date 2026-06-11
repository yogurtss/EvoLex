from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from evolex.agents.deepseek_client import BaseExtractor
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


PipelineAlias = Literal["phase1", "phase1+2", "phase2", "full"]


def run_phase1_text(
    document_text: str,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
) -> Phase1RunResult:
    result = run_pipeline_text(
        document_text=document_text,
        pipeline="phase1",
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
    )
    assert isinstance(result, Phase1RunResult)
    return result


def run_phase1_file(
    path: Path,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
) -> Phase1RunResult:
    result = run_pipeline_file(
        path=path,
        pipeline="phase1",
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
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


def run_phase2_text(
    document_text: str,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
) -> Phase2RunResult:
    result = run_pipeline_text(
        document_text=document_text,
        pipeline="phase1+2",
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
    )
    assert isinstance(result, Phase2RunResult)
    return result


def run_phase2_file(
    path: Path,
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
) -> Phase2RunResult:
    result = run_pipeline_file(
        path=path,
        pipeline="phase1+2",
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
    )
    assert isinstance(result, Phase2RunResult)
    return result


def run_pipeline_text(
    document_text: str,
    pipeline: PipelineAlias = "phase1",
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
) -> Phase1RunResult | Phase2RunResult:
    pipeline_mode = normalize_pipeline(pipeline)
    run_id = f"RUN-{uuid4().hex[:12]}"
    document_id = f"DOC-{uuid4().hex[:12]}"
    graph = build_graph(
        extractor=extractor,
        output_dir=output_dir,
        pipeline=pipeline_mode,
        on_event=on_event,
    )
    state = graph.invoke(
        {
            "run_id": run_id,
            "thread_id": f"document:{document_id}:{_thread_version(pipeline_mode)}",
            "document_id": document_id,
            "document_text": document_text,
            "llm_call_count": 0,
            "status": "running",
        },
        on_node=on_node,
    )
    if pipeline_mode == "phase1+2":
        return _to_phase2_result(state)
    return _to_result(state)


def run_pipeline_file(
    path: Path,
    pipeline: PipelineAlias = "phase1",
    output_dir: Path | None = None,
    extractor: BaseExtractor | None = None,
    on_node: Callable[[str], None] | None = None,
    on_event: GraphLogCallback | None = None,
) -> Phase1RunResult | Phase2RunResult:
    document_text = path.read_text(encoding="utf-8")
    return run_pipeline_text(
        document_text=document_text,
        pipeline=pipeline,
        output_dir=output_dir,
        extractor=extractor,
        on_node=on_node,
        on_event=on_event,
    )


# -- helpers ------------------------------------------------------------------


def normalize_pipeline(pipeline: PipelineAlias | str) -> PipelineMode:
    normalized = pipeline.lower().replace("_", "-").replace(" ", "")
    if normalized in ("phase1", "p1"):
        return "phase1"
    if normalized in ("phase1+2", "phase2", "p2", "full"):
        return "phase1+2"
    msg = "pipeline must be one of: phase1, phase1+2, phase2, full"
    raise ValueError(msg)


def _thread_version(pipeline: PipelineMode) -> str:
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
