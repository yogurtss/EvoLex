from __future__ import annotations

from typing import Literal, TypedDict


class GraphState(TypedDict, total=False):
    run_id: str
    thread_id: str
    document_id: str
    document_text: str
    document_type: str
    domains: list[str]
    segments: list[dict]
    semantic_atoms: list[dict]
    validation_results: list[dict]
    candidate_output_path: str
    # Phase II fields
    entities: list[dict]
    relations: list[dict]
    quality_scores: list[dict]
    publish_output_path: str
    # Shared
    warnings: list[str]
    llm_call_count: int
    status: Literal["running", "candidate", "quarantined", "failed", "published"]
