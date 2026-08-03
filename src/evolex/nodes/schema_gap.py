from __future__ import annotations

from pathlib import Path

from evolex.graph.state import GraphState
from evolex.nodes.relation_merge import canonicalize_predicate
from evolex.repositories.schema_store import (
    BASE_ATTRIBUTES,
    BASE_PREDICATES,
    BASE_TYPES,
    SchemaCandidateStore,
)

# A hard-coded "known types" set for gap detection.
# In a full implementation this would come from a Schema Registry.
KNOWN_TYPES: set[str] = set(BASE_TYPES)
KNOWN_PREDICATES: set[str] = set(BASE_PREDICATES)


def schema_gap_node(state: GraphState) -> dict:
    return _schema_gap_node(
        state,
        known_types=KNOWN_TYPES,
        known_predicates=KNOWN_PREDICATES,
        known_parameters=set(BASE_ATTRIBUTES),
        active_schema_version=state.get("schema_version", ""),
    )


def make_schema_gap_node(schema_dir: Path | None = None):
    def active_schema_gap_node(state: GraphState) -> dict:
        pinned = state.get("active_schema")
        active = (
            dict(pinned)
            if isinstance(pinned, dict) and pinned.get("version_id")
            else SchemaCandidateStore(schema_dir).get_active_schema()
        )
        return _schema_gap_node(
            state,
            known_types=set(active.get("types", [])),
            known_predicates=set(active.get("predicates", [])),
            known_parameters=set(active.get("attributes", [])),
            active_schema_version=str(active.get("version_id", "")),
        )

    return active_schema_gap_node


def _schema_gap_node(
    state: GraphState,
    *,
    known_types: set[str],
    known_predicates: set[str],
    known_parameters: set[str],
    active_schema_version: str,
) -> dict:
    """Detect mentions/claims that cannot be mapped to known schema types.

    Scans claims and mentions for subjects, predicates, and objects that
    do not match known types or predicates, and emits unresolved_terms.
    """
    run_id = state.get("run_id", "")
    schema_version = active_schema_version or state.get("schema_version", "")

    unresolved_terms: list[dict] = []

    # Check claims for unknown predicate patterns
    canonical_known_predicates = {
        canonicalize_predicate(str(item)) for item in known_predicates
    }
    for claim in state.get("claim_candidates", []):
        raw_predicate = str(claim.get("predicate", ""))
        predicate = canonicalize_predicate(raw_predicate)
        if predicate and predicate not in canonical_known_predicates:
            unresolved_terms.append({
                "term": predicate,
                "category": "predicate",
                "source": "claim_candidate",
                "context": (
                    f"{claim.get('subject', '')} {raw_predicate} "
                    f"{claim.get('object', '')}"
                ),
                "raw_term": raw_predicate,
                "run_id": run_id,
                "schema_version": schema_version,
                "evidence": claim.get("evidence_ids", []),
            })

    # Check mentions for unknown types
    for mention in state.get("mentions", []):
        mtype = mention.get("mention_type", "")
        if mtype and mtype not in known_types:
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
        "schema_version": schema_version,
        "active_schema": {
            "version_id": schema_version,
            "types": sorted(known_types),
            "predicates": sorted(known_predicates),
            "attributes": sorted(known_parameters),
        },
    }
