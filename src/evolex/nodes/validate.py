from __future__ import annotations

from evolex.graph.state import GraphState

REQUIRED_ATOM_FIELDS = {"type", "text", "evidence", "confidence", "segment_id"}


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

    # Preserve "failed" status from earlier nodes (e.g. empty text)
    existing_status = state.get("status", "running")
    if existing_status == "failed":
        status = "failed"
    elif valid_atoms:
        status = "candidate"
    else:
        status = "quarantined"
    return {
        "semantic_atoms": valid_atoms,
        "validation_results": results,
        "status": status,
    }
