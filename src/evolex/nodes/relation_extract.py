from __future__ import annotations

from evolex.agents.deepseek_client import BaseExtractor
from evolex.graph.state import GraphState


def make_relation_extract_node(extractor: BaseExtractor):
    """Create a relation extraction node.

    Uses LLM when available (DeepSeekExtractor), otherwise falls back to
    proximity-based heuristic extraction.
    """

    def relation_extract_node(state: GraphState) -> dict:
        atoms = state.get("semantic_atoms", [])
        entities = state.get("entities", [])
        relation_candidates = state.get("relation_candidates", [])
        llm_call_count = state.get("llm_call_count", 0)
        warnings: list[str] = list(state.get("warnings", []))

        if not entities:
            return {"relations": [], "warnings": warnings}

        relations = _materialize_joint_relations(
            relation_candidates,
            state.get("mention_entity_map", {}),
        )
        mention_entity_map = state.get("mention_entity_map", {})
        rejected_candidates = []
        for item in relation_candidates:
            subject_entity_id = mention_entity_map.get(
                str(item.get("subject_mention_id", ""))
            )
            object_entity_id = mention_entity_map.get(
                str(item.get("object_mention_id", ""))
            )
            if (
                item.get("endpoint_validation_status") == "invalid"
                or not subject_entity_id
                or not object_entity_id
                or subject_entity_id == object_entity_id
            ):
                rejected = dict(item)
                errors = list(rejected.get("endpoint_validation_errors", []))
                if subject_entity_id and subject_entity_id == object_entity_id:
                    errors.append("canonical_endpoint_collapse")
                if not errors:
                    errors.append("unresolved_endpoint_after_entity_resolution")
                rejected["endpoint_validation_errors"] = errors
                rejected_candidates.append(rejected)
        if relation_candidates and not relations:
            warnings.append(
                "Joint relation candidates were present but none had two resolved endpoints."
            )
        elif rejected_candidates:
            warnings.append(
                f"{len(rejected_candidates)} of {len(relation_candidates)} joint relation "
                "candidates were held because one or both mention endpoints were unresolved."
            )

        if relations:
            extraction_mode = "joint"
        elif not atoms:
            extraction_mode = "none"
        elif extractor.supports_relation_extraction:
            relations, llm_call_count, warnings = _llm_extract(
                extractor, atoms, entities, llm_call_count, warnings
            )
            extraction_mode = "relation_fallback"
        else:
            relations = _heuristic_extract(atoms, entities)
            extraction_mode = "heuristic_fallback"

        return {
            "relations": relations,
            "relation_extraction_mode": extraction_mode,
            "joint_relation_yield": len(relations) if extraction_mode == "joint" else 0,
            "relation_endpoint_failures": [
                {
                    "relation_candidate_id": item.get(
                        "relation_candidate_id", ""
                    ),
                    "subject_mention_id": item.get("subject_mention_id", ""),
                    "object_mention_id": item.get("object_mention_id", ""),
                    "errors": item.get(
                        "endpoint_validation_errors",
                        ["unresolved_endpoint_after_entity_resolution"],
                    ),
                }
                for item in rejected_candidates
            ],
            "llm_call_count": llm_call_count,
            "warnings": warnings,
        }

    return relation_extract_node


def _llm_extract(
    extractor: BaseExtractor,
    atoms: list[dict],
    entities: list[dict],
    llm_call_count: int,
    warnings: list[str],
) -> tuple[list[dict], int, list[str]]:
    """Use the LLM extractor to identify relations between atoms."""
    try:
        relations = extractor.extract_relations(atoms, entities)
        llm_call_count += 1
        return relations, llm_call_count, warnings

    except Exception as exc:
        warnings.append(f"Relation extraction LLM call failed: {exc}. Falling back to heuristic.")
        relations = _heuristic_extract(atoms, entities)
        return relations, llm_call_count, warnings


def _heuristic_extract(atoms: list[dict], entities: list[dict]) -> list[dict]:
    """Proximity-based heuristic relation extraction.

    Atoms co-occurring in the same segment with measurement/property types
    get related via has_measurement / has_property predicates.
    Only consumes entities that have been LINKed or CREATE_CANDIDATE.
    """
    # Build lookup: segment_id -> list of atom indices with their entity ids
    entity_by_atom_idx: dict[int, str] = {}
    for ent in entities:
        for idx in ent.get("source_atom_indices", []):
            entity_by_atom_idx[idx] = ent["entity_id"]

    # Group atoms by segment
    segment_atoms: dict[str, list[int]] = {}
    for idx, atom in enumerate(atoms):
        seg_id = atom.get("segment_id", "")
        segment_atoms.setdefault(seg_id, []).append(idx)

    relations: list[dict] = []
    rel_idx = 0

    for _seg_id, atom_indices in segment_atoms.items():
        if len(atom_indices) < 2:
            continue

        entities_in_seg = [
            (idx, entity_by_atom_idx[idx])
            for idx in atom_indices
            if idx in entity_by_atom_idx
        ]
        measurements = [
            (idx, eid) for idx, eid in entities_in_seg
            if atoms[idx].get("type") == "measurement"
        ]
        properties = [
            (idx, eid) for idx, eid in entities_in_seg
            if atoms[idx].get("type") == "property"
        ]

        # Link measurements and properties to other entities in same segment
        for meas_idx, meas_eid in measurements:
            for other_idx, other_eid in entities_in_seg:
                if other_idx == meas_idx:
                    continue
                rel_idx += 1
                relations.append({
                    "relation_id": f"rel-{rel_idx:04d}",
                    "subject_entity_id": other_eid,
                    "predicate": "has_measurement",
                    "object_entity_id": meas_eid,
                    "evidence": atoms[meas_idx].get("evidence", ""),
                    "confidence": 0.55,
                })

        for prop_idx, prop_eid in properties:
            for other_idx, other_eid in entities_in_seg:
                if other_idx == prop_idx:
                    continue
                rel_idx += 1
                relations.append({
                    "relation_id": f"rel-{rel_idx:04d}",
                    "subject_entity_id": other_eid,
                    "predicate": "has_property",
                    "object_entity_id": prop_eid,
                    "evidence": atoms[prop_idx].get("evidence", ""),
                    "confidence": 0.55,
                })

    return relations


def _materialize_joint_relations(
    candidates: list[dict],
    mention_entity_map: dict[str, str],
) -> list[dict]:
    """Resolve mention-scoped endpoints without asking the model again."""
    relations: list[dict] = []
    for candidate in candidates:
        if candidate.get("endpoint_validation_status") == "invalid":
            continue
        subject_mention_id = str(candidate.get("subject_mention_id", ""))
        object_mention_id = str(candidate.get("object_mention_id", ""))
        subject_entity_id = mention_entity_map.get(subject_mention_id)
        object_entity_id = mention_entity_map.get(object_mention_id)
        if not subject_entity_id or not object_entity_id:
            continue
        if subject_entity_id == object_entity_id:
            continue
        relations.append(
            {
                "relation_id": f"rel-{len(relations) + 1:04d}",
                "subject_entity_id": subject_entity_id,
                "predicate": str(candidate.get("predicate", "related_to")),
                "object_entity_id": object_entity_id,
                "evidence": str(candidate.get("evidence", "")),
                "evidence_ids": list(candidate.get("evidence_ids", [])),
                "source_relation_candidate_ids": [
                    str(candidate.get("relation_candidate_id", ""))
                ],
                "segment_ids": [str(candidate.get("segment_id", ""))],
                "confidence": float(candidate.get("confidence", 0.5)),
                "extraction_mode": "joint",
            }
        )
    return relations


def _resolve_entity_decisions(
    entities: list[dict],
    entity_decisions: list[dict],
) -> list[dict]:
    """Filter entities, keeping only those with LINK or CREATE_CANDIDATE decisions.

    Returns a new entity list with AMBIGUOUS/REJECT entries excluded.
    """
    valid_entity_ids: set[str] = set()
    for d in entity_decisions:
        if d.get("decision") in ("LINK", "CREATE_CANDIDATE"):
            eid = d.get("target_entity_id")
            if eid:
                valid_entity_ids.add(eid)

    return [e for e in entities if e.get("entity_id") in valid_entity_ids]
