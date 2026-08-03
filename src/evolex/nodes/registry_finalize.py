from __future__ import annotations

from pathlib import Path

from evolex.graph.state import GraphState
from evolex.repositories.candidates import CandidateRegistry
from evolex.repositories.schema_store import SchemaCandidateStore


def make_registry_finalize_node(output_dir: Path | None = None):
    registry_dir = (output_dir / "registry") if output_dir else None
    schema_dir = (output_dir / "schema_candidates") if output_dir else None

    def registry_finalize_node(state: GraphState) -> dict:
        run_id = state["run_id"]
        registry = CandidateRegistry(registry_dir)

        action = _policy_action(state)
        quarantine_record = (
            _quarantine_record(state)
            if action == "quarantine" or state.get("status") == "quarantined"
            else None
        )
        candidates = _candidate_snapshot(state)
        registry.replace_run_snapshot(
            run_id,
            entity_decisions=list(state.get("entity_decisions", [])),
            policy_decisions=list(state.get("policy_decisions", [])),
            audit_events=list(state.get("audit_events", [])),
            merge_decisions=list(state.get("merge_decisions", [])),
            agent_trace=list(state.get("agent_trace", [])),
            candidates=candidates,
            quarantine_record=quarantine_record,
        )

        schema_store = SchemaCandidateStore(schema_dir)
        for proposal in state.get("schema_proposals", []):
            schema_store.put_proposal(proposal)

        return {"registry_output_path": str(registry._db_path(run_id))}

    return registry_finalize_node


def _candidate_snapshot(state: GraphState) -> list[tuple[str, dict]]:
    """Build the complete candidate projection that finalization replaces.

    ``candidate_store`` writes typed candidates early in the pipeline.  Because
    finalization intentionally replaces the whole run projection for
    idempotence, it must carry those objects forward as well as the later
    evolution artefacts.
    """
    candidates: list[tuple[str, dict]] = []
    for object_type, state_key in (
        ("atom", "semantic_atoms"),
        ("mention", "mentions"),
        ("measurement", "measurements"),
        ("condition", "conditions"),
        ("claim", "claim_candidates"),
        ("evidence", "evidence_spans"),
    ):
        candidates.extend(
            (object_type, value)
            for value in state.get(state_key, [])
            if isinstance(value, dict) and value
        )

    candidates.extend(
        (object_type, value)
        for object_type, value in (
            ("graph_patch", state.get("graph_patch")),
            ("shadow_evaluation", state.get("shadow_evaluation")),
            ("evolution_decision", state.get("evolution_decision")),
            ("evolution_commit", state.get("evolution_commit")),
        )
        if isinstance(value, dict) and value
    )
    return candidates


def _policy_action(state: GraphState) -> str:
    decisions = state.get("policy_decisions", [])
    if not decisions:
        return ""
    return str(decisions[0].get("action", ""))


def _quarantine_record(state: GraphState) -> dict:
    decision = state.get("policy_decisions", [{}])[0] if state.get("policy_decisions") else {}
    reasons = decision.get("reasons", []) or state.get("warnings", []) or ["policy_quarantine"]
    evidence = ""
    evidence_spans = state.get("evidence_spans", [])
    if evidence_spans:
        evidence = str(evidence_spans[0].get("text", ""))
    return {
        "object_type": "run",
        "object_id": state.get("run_id", ""),
        "reason": ", ".join(str(reason) for reason in reasons),
        "risk_level": str(decision.get("risk_level", decision.get("change_type", "medium"))),
        "evidence": evidence,
        "suggested_action": "review evidence, schema proposals, and critic results before publishing",
    }
