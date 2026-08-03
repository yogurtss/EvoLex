from __future__ import annotations

from evolex.graph.state import GraphState

REQUIRED_ATOM_FIELDS = {"type", "text", "evidence", "confidence", "segment_id"}

# Phase III claim/evidence validation
REQUIRED_CLAIM_FIELDS = {"subject", "predicate", "object", "evidence_ids"}
REQUIRED_EVIDENCE_FIELDS = {"evidence_id", "document_id", "text"}
REQUIRED_RELATION_CANDIDATE_FIELDS = {
    "relation_candidate_id",
    "subject_mention_id",
    "predicate",
    "object_mention_id",
    "evidence_ids",
}


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

    # Evidence must be sanitized before claims are allowed to reference it.
    valid_evidence: list[dict] = []
    evidence_validation_results: list[dict] = []
    for index, ev in enumerate(state.get("evidence_spans", [])):
        missing_fields = sorted(
            field
            for field in REQUIRED_EVIDENCE_FIELDS
            if field not in ev or not str(ev.get(field, "")).strip()
        )
        ok = not missing_fields
        evidence_validation_results.append({
            "evidence_index": index,
            "ok": ok,
            "missing_fields": missing_fields,
        })
        if ok:
            valid_evidence.append(ev)

    valid_evidence_ids = {
        str(ev["evidence_id"]) for ev in valid_evidence
    }

    # Validate claims only against the filtered evidence set.
    valid_claims: list[dict] = []
    claim_validation_results: list[dict] = []
    for index, claim in enumerate(state.get("claim_candidates", [])):
        missing_fields = sorted(
            field
            for field in REQUIRED_CLAIM_FIELDS
            if field not in claim
            or (
                field != "evidence_ids"
                and not str(claim.get(field, "")).strip()
            )
        )
        evidence_ids = {
            str(item)
            for item in claim.get("evidence_ids", [])
            if str(item).strip()
        }
        has_evidence = (
            len(evidence_ids) >= 1
            and evidence_ids.issubset(valid_evidence_ids)
        )
        ok = not missing_fields and has_evidence
        claim_validation_results.append({
            "claim_index": index,
            "ok": ok,
            "missing_fields": missing_fields,
            "has_evidence": has_evidence,
        })
        if ok:
            valid_claims.append(claim)

    # Apply the same evidence-first reference check to joint relation
    # candidates before endpoint materialization.
    valid_relation_candidates: list[dict] = []
    relation_reference_results: list[dict] = []
    relation_evidence_failures: list[dict] = []
    for index, candidate in enumerate(state.get("relation_candidates", [])):
        missing_fields = sorted(
            field
            for field in REQUIRED_RELATION_CANDIDATE_FIELDS
            if field not in candidate
            or (
                field != "evidence_ids"
                and not str(candidate.get(field, "")).strip()
            )
        )
        evidence_ids = {
            str(item)
            for item in candidate.get("evidence_ids", [])
            if str(item).strip()
        }
        has_evidence = (
            len(evidence_ids) >= 1
            and evidence_ids.issubset(valid_evidence_ids)
        )
        ok = not missing_fields and has_evidence
        result = {
            "relation_candidate_index": index,
            "relation_candidate_id": candidate.get(
                "relation_candidate_id", ""
            ),
            "ok": ok,
            "missing_fields": missing_fields,
            "has_evidence": has_evidence,
            "invalid_evidence_ids": sorted(evidence_ids - valid_evidence_ids),
        }
        relation_reference_results.append(result)
        if ok:
            valid_relation_candidates.append(candidate)
        else:
            relation_evidence_failures.append(
                {
                    "relation_candidate_id": candidate.get(
                        "relation_candidate_id", ""
                    ),
                    "errors": [
                        *(
                            ["missing_required_fields"]
                            if missing_fields
                            else []
                        ),
                        *(
                            ["invalid_or_missing_evidence_reference"]
                            if not has_evidence
                            else []
                        ),
                    ],
                    "missing_fields": missing_fields,
                    "invalid_evidence_ids": sorted(
                        evidence_ids - valid_evidence_ids
                    ),
                }
            )

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
        "claim_candidates": valid_claims,
        "evidence_spans": valid_evidence,
        "relation_candidates": valid_relation_candidates,
        "relation_evidence_failures": relation_evidence_failures,
        "validation_results": (
            results
            + claim_validation_results
            + evidence_validation_results
            + relation_reference_results
        ),
        "status": status,
    }

    return update
