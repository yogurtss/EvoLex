from __future__ import annotations

from typing import Literal, TypedDict


class GraphState(TypedDict, total=False):
    # -- run identity --
    run_id: str
    thread_id: str
    document_id: str
    document_version: int
    pipeline_mode: str

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
    relation_candidates: list[dict]
    relation_endpoint_failures: list[dict]
    relation_evidence_failures: list[dict]
    relation_extraction_mode: str
    joint_relation_yield: int
    quality_scores: list[dict]
    publish_output_path: str

    # -- Phase III typed-object fields --
    mentions: list[dict]
    measurements: list[dict]
    conditions: list[dict]
    claim_candidates: list[dict]
    evidence_spans: list[dict]
    entity_decisions: list[dict]
    mention_entity_map: dict[str, str]
    entity_merge_proposals: list[dict]
    relation_merge_proposals: list[dict]
    relation_identity_hypotheses: list[dict]
    relation_conflicts: list[dict]
    merge_decisions: list[dict]
    canonical_baseline: dict
    graph_patch: dict
    canonical_entity_map: dict[str, str]
    shadow_evaluation: dict
    causal_validation_certificate: dict
    evolution_decision: dict
    evolution_commit: dict
    canonical_store_path: str
    canonical_version_id: str
    policy_decisions: list[dict]
    critic_results: list[dict]
    schema_proposals: list[dict]
    active_schema: dict
    unresolved_terms: list[dict]
    registry_output_path: str
    audit_events: list[dict]
    agent_trace: list[dict]
    completed_tools: list[str]
    invalidated_tools: list[str]
    tool_revisions: dict[str, int]
    low_eig_rounds: int
    governance_incomplete: bool
    uncertainty_scores: dict[str, float]
    information_gain_scores: list[dict]
    graph_quality_metrics: dict[str, float]
    publish_confidence: float
    agent_budget: dict
    active_questions: list[dict]
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
