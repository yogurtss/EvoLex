from __future__ import annotations

from evolex.graph.state import GraphState

REQUIRED_ATOM_FIELDS = {"type", "text", "evidence", "confidence", "segment_id"}

# Phase III claim/evidence validation
REQUIRED_CLAIM_FIELDS = {"subject", "predicate", "object", "evidence_ids"}
REQUIRED_EVIDENCE_FIELDS = {"evidence_id", "document_id", "text"}


def validate_node(state: GraphState) -> dict:
    results: list[dict] = []
    valid_atoms: list[dict] = []

    for index, atom in enumerate(state.get("semantic_atoms", [])):
        missing_fields = sorted(REQUIRED_ATOM_FIELDS - set(atom))
        confidence = atom.get("confidence")
        confidence_valid = isinstance(confidence, int | float) and 0 <= confidence <= 1
        ok = not missing_fields and confidence_valid

        results.append(
            {
                "atom_index": index,
                "ok": ok,
                "missing_fields": missing_fields,
                "confidence_valid": confidence_valid,
            }
        )
        if ok:
            valid_atoms.append(atom)

    # Validate claim_candidates (Phase III)
    valid_claims: list[dict] = []
    claim_validation_results: list[dict] = []
    for index, claim in enumerate(state.get("claim_candidates", [])):
        missing_fields = sorted(REQUIRED_CLAIM_FIELDS - set(claim))
        evidence_ids = set(claim.get("evidence_ids", []))
        existing_evidence_ids = {
            ev.get("evidence_id") for ev in state.get("evidence_spans", [])
        }
        has_evidence = len(evidence_ids) >= 1 and evidence_ids.issubset(existing_evidence_ids)
        ok = not missing_fields and has_evidence
        claim_validation_results.append({
            "claim_index": index,
            "ok": ok,
            "missing_fields": missing_fields,
            "has_evidence": has_evidence,
        })
        if ok:
            valid_claims.append(claim)

    # Validate evidence_spans (Phase III)
    valid_evidence: list[dict] = []
    evidence_validation_results: list[dict] = []
    for index, ev in enumerate(state.get("evidence_spans", [])):
        missing_fields = sorted(REQUIRED_EVIDENCE_FIELDS - set(ev))
        ok = not missing_fields
        evidence_validation_results.append({
            "evidence_index": index,
            "ok": ok,
            "missing_fields": missing_fields,
        })
        if ok:
            valid_evidence.append(ev)

    # Preserve "failed" status from earlier nodes (e.g. empty text)
    existing_status = state.get("status", "running")
    if existing_status == "failed":
        status = "failed"
    elif valid_atoms or valid_claims:
        status = "candidate"
    else:
        status = "quarantined"

    update: dict = {
        "semantic_atoms": valid_atoms,
        "validation_results": results + claim_validation_results + evidence_validation_results,
        "status": status,
    }
    if valid_claims or valid_evidence:
        update["claim_candidates"] = valid_claims
        update["evidence_spans"] = valid_evidence

    return update
