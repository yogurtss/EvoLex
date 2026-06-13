from __future__ import annotations

from evolex.graph.state import GraphState

# A hard-coded "known types" set for gap detection.
# In a full implementation this would come from a Schema Registry.
KNOWN_TYPES: set[str] = {
    "entity", "process", "material", "tool", "measurement",
    "property", "claim", "event", "condition",
}

KNOWN_PREDICATES: set[str] = {
    "has_measurement", "has_property", "depends_on", "related_to",
    "has_condition", "has_parameter", "affects", "increases",
    "decreases", "part_of",
}


def schema_gap_node(state: GraphState) -> dict:
    """Detect mentions/claims that cannot be mapped to known schema types.

    Scans claims and mentions for subjects, predicates, and objects that
    do not match known types or predicates, and emits unresolved_terms.
    """
    run_id = state.get("run_id", "")
    schema_version = state.get("schema_version", "")

    unresolved_terms: list[dict] = []

    # Check claims for unknown predicate patterns
    for claim in state.get("claim_candidates", []):
        predicate = claim.get("predicate", "")
        if predicate and predicate not in KNOWN_PREDICATES:
            unresolved_terms.append({
                "term": predicate,
                "category": "predicate",
                "source": "claim_candidate",
                "context": f"{claim.get('subject', '')} {predicate} {claim.get('object', '')}",
                "run_id": run_id,
                "schema_version": schema_version,
                "evidence": claim.get("evidence_ids", []),
            })

    # Check mentions for unknown types
    for mention in state.get("mentions", []):
        mtype = mention.get("mention_type", "")
        if mtype and mtype not in KNOWN_TYPES:
            unresolved_terms.append({
                "term": mention.get("text", ""),
                "category": f"mention_type:{mtype}",
                "source": "mention",
                "context": mention.get("evidence", ""),
                "run_id": run_id,
                "schema_version": schema_version,
                "evidence": [mention.get("segment_id", "")],
            })

    # Check measurements for unknown parameters
    known_parameters = {"time", "temperature", "pressure", "voltage", "current", "rate", "percentage"}
    for measurement in state.get("measurements", []):
        param = measurement.get("parameter", "")
        if param and param not in known_parameters:
            unresolved_terms.append({
                "term": param,
                "category": "new_parameter",
                "source": "measurement",
                "context": f"{param}={measurement.get('value', '')}{measurement.get('unit', '')}",
                "run_id": run_id,
                "schema_version": schema_version,
                "evidence": [measurement.get("segment_id", "")],
            })

    return {
        "unresolved_terms": unresolved_terms,
    }
