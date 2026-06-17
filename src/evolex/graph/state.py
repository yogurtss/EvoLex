from __future__ import annotations

from typing import Literal, TypedDict


class GraphState(TypedDict, total=False):
    # -- run identity --
    run_id: str
    thread_id: str
    document_id: str
    document_version: int

    # -- version pins (for reproducibility) --
    schema_version: str
    policy_version: str
    prompt_versions: dict[str, str]
    model_routes: dict[str, str]
    graph_version: str

    # -- document --
    document_text: str
    document_type: str
    domains: list[str]
    segments: list[dict]

    # -- legacy atom fields (kept for backward compat) --
    semantic_atoms: list[dict]
    validation_results: list[dict]
    candidate_output_path: str

    # -- Phase II legacy fields --
    entities: list[dict]
    relations: list[dict]
    quality_scores: list[dict]
    publish_output_path: str

    # -- Phase III typed-object fields --
    mentions: list[dict]
    measurements: list[dict]
    conditions: list[dict]
    claim_candidates: list[dict]
    evidence_spans: list[dict]
    entity_decisions: list[dict]
    policy_decisions: list[dict]
    critic_results: list[dict]
    schema_proposals: list[dict]
    unresolved_terms: list[dict]
    registry_output_path: str
    audit_events: list[dict]
    evaluation_mode: str
    baseline_run_id: str
    checkpoint_path: str
    shadow_report_path: str

    # -- shared --
    warnings: list[str]
    llm_call_count: int
    tool_call_count: int
    retry_count: int
    status: Literal[
        "running", "candidate", "published",
        "quarantined", "rejected", "failed",
    ]
