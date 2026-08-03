from __future__ import annotations

from evolex.graph.state import GraphState

def critic_node(state: GraphState) -> dict:
    """Semantic critic: verify evidence sufficiency and basic consistency.

    Examines claims and their linked evidence, then produces critic_results
    with an approved/rejected verdict for each claim.
    """
    claims = state.get("claim_candidates", [])
    evidence_spans = state.get("evidence_spans", [])
    evidence_by_id = {ev.get("evidence_id"): ev for ev in evidence_spans}

    critic_results: list[dict] = []
    for idx, claim in enumerate(claims):
        issues: list[str] = []

        # Check evidence linkage
        evidence_ids = claim.get("evidence_ids", [])
        if not evidence_ids:
            issues.append("no_evidence")
        else:
            for eid in evidence_ids:
                if eid not in evidence_by_id:
                    issues.append(f"missing_evidence:{eid}")

        # Check that at least one measurement exists if conditions are present
        conditions = claim.get("conditions", [])
        measurements = claim.get("measurements", [])
        if conditions and not measurements:
            issues.append("conditions_without_measurements")

        # Check confidence threshold
        confidence = float(claim.get("confidence", 0.5))
        if confidence < 0.3:
            issues.append("low_confidence")

        verdict = "approved" if not issues else "rejected"
        critic_results.append({
            "claim_index": idx,
            "claim_id": claim.get("claim_id", ""),
            "verdict": verdict,
            "issues": issues,
            "confidence": confidence,
        })

    return {
        "critic_results": critic_results,
        "status": state.get("status", "running"),
    }
