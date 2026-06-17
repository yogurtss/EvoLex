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

        for decision in state.get("entity_decisions", []):
            registry.put_entity_decision(run_id, decision)

        for decision in state.get("policy_decisions", []):
            registry.put_policy_decision(run_id, decision)

        for event in state.get("audit_events", []):
            registry.put_audit_event(run_id, event)

        action = _policy_action(state)
        if action == "quarantine" or state.get("status") == "quarantined":
            registry.put_quarantine(run_id, _quarantine_record(state))

        schema_store = SchemaCandidateStore(schema_dir)
        for proposal in state.get("schema_proposals", []):
            schema_store.put_proposal(proposal)

        return {"registry_output_path": str(registry._db_path(run_id))}

    return registry_finalize_node


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
