from __future__ import annotations

from evolex.graph.state import GraphState
from evolex.policy.engine import assess_risk, decide_policy


def policy_node(state: GraphState) -> dict:
    """Policy decision node.

    Collects signals from validator results, critic results, and
    schema proposals, then decides the routing action.
    """
    # Gather signals from state
    validation_results = state.get("validation_results", [])
    critic_results = state.get("critic_results", [])
    schema_proposals = state.get("schema_proposals", [])

    # Compute deterministic_violations from validation
    deterministic_violations = any(
        not r.get("ok", True) for r in validation_results
    )

    # Compute critic_approved from critic results
    approved = [r for r in critic_results if r.get("verdict") == "approved"]
    total = len(critic_results)
    critic_approved = approved and (len(approved) / max(total, 1)) >= 0.5

    # Evidence coverage: at least one evidence per claim
    claims = state.get("claim_candidates", [])
    evidence_spans = state.get("evidence_spans", [])
    evidence_coverage = len(evidence_spans) / max(len(claims), 1)

    # Change type detection
    change_type = "new_instance"
    if schema_proposals:
        # Determine risk level from proposals
        for prop in schema_proposals:
            ptype = prop.get("proposal_type", "new_type")
            if ptype in ("type_merge", "type_split", "delete", "batch_migration"):
                change_type = ptype
                break
            if ptype in ("new_type", "new_relation"):
                change_type = ptype

    signals = {
        "deterministic_violations": deterministic_violations,
        "critic_approved": critic_approved,
        "evidence_coverage": evidence_coverage,
        "independent_document_count": 1,
        "change_type": change_type,
    }

    action = decide_policy(signals)
    risk_level = assess_risk(signals)
    reasons: list[str] = []
    evolution_decision = state.get("evolution_decision")
    evolution_gate_passed = (
        bool(evolution_decision.get("accepted"))
        if isinstance(evolution_decision, dict)
        else None
    )
    relation_conflicts = state.get("relation_conflicts", [])
    relation_endpoint_failures = state.get("relation_endpoint_failures", [])

    if evolution_gate_passed is False and action == "publish":
        action = "candidate"
        reasons.append("evolution_shadow_gate_not_accepted")
    if relation_conflicts:
        action = "quarantine"
        reasons.append("unresolved_functional_relation_conflict")
    if relation_endpoint_failures and action == "publish":
        action = "candidate"
        reasons.append("unresolved_joint_relation_endpoint")

    if deterministic_violations:
        reasons.append("deterministic_validation_failed")
    if not critic_approved and critic_results:
        reasons.append("critic_not_approved")
    if evidence_coverage < 1.0:
        reasons.append(f"evidence_coverage={evidence_coverage:.2f}")

    policy_decisions: list[dict] = [
        {
            "action": action,
            "policy_engine_action": action,
            "canonical_action": "pending",
            "delivery_action": "pending",
            "risk_level": risk_level,
            "reasons": reasons,
            "evidence_coverage": evidence_coverage,
            "critic_approved": critic_approved,
            "change_type": change_type,
            "evolution_gate_passed": evolution_gate_passed,
            "relation_conflict_count": len(relation_conflicts),
            "relation_endpoint_failure_count": len(relation_endpoint_failures),
        }
    ]

    # A policy action is an authorization, not a completed delivery outcome.
    # In particular, "publish" must not make an intermediate checkpoint look
    # published before the canonical commit and run-level publish both finish.
    status_map = {
        "publish": "candidate",
        "candidate": "candidate",
        "quarantine": "quarantined",
        "reject": "rejected",
    }
    new_status = status_map.get(action, "candidate")

    return {
        "policy_decisions": policy_decisions,
        "status": new_status,
    }
