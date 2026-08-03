from __future__ import annotations

import re
from copy import deepcopy

from evolex.graph.state import GraphState

# --- alias normalisation maps ---

ALIAS_MAP: dict[str, str] = {
    "api gw": "api gateway",
    "api_gw": "api gateway",
    "apigw": "api gateway",
    "gw": "gateway",
    "svc": "service",
    "db": "database",
    "config": "configuration",
}

# Unit synonyms that should normalise to the same entity
UNIT_SYNONYM_TABLE: dict[str, str] = {
    "ms": "ms",
    "msec": "ms",
    "milliseconds": "ms",
    "millisecond": "ms",
    "s": "s",
    "sec": "s",
    "second": "s",
    "seconds": "s",
    "mtorr": "mTorr",
    "mt": "mTorr",
    "°c": "°C",
    "celsius": "°C",
    "%": "%",
    "percent": "%",
}


def entity_resolve_node(state: GraphState) -> dict:
    """Resolve mentions to entities with decision records.

    Uses mention texts (from ``mentions``) or falls back to ``semantic_atoms``.
    Outputs both ``entity_decisions`` (one per mention) and ``entities``
    (the successfully resolved entities).
    """
    run_id = state.get("run_id", "")
    document_id = state.get("document_id", "")
    document_version = state.get("document_version", 0)

    # Determine input source – prefer typed mentions
    mentions: list[dict]
    if state.get("mentions"):
        mentions = deepcopy(state["mentions"])
    elif state.get("semantic_atoms"):
        mentions = [
            _atom_to_mention(atom, atom_index)
            for atom_index, atom in enumerate(state["semantic_atoms"])
        ]
    else:
        return {"entities": [], "entity_decisions": []}

    # Normalise aliases and units in mention text
    for m in mentions:
        m["normalized_text"] = _normalize_entity_text(m.get("normalized_text", m.get("text", "")))

    # --- resolution pass ---
    entity_decisions: list[dict] = []
    seen_normalised: dict[tuple[str, str], int] = {}
    entities: list[dict] = []
    next_entity_num = 1

    for idx, mention in enumerate(mentions):
        text = mention.get("text", "")
        norm_text = mention.get("normalized_text", _normalize_entity_text(text))
        mention_type = mention.get("mention_type", mention.get("type", "entity"))
        mention_id = str(mention.get("mention_id", f"legacy:{idx}"))
        segment_id = mention.get("segment_id", "")
        confidence = float(mention.get("confidence", 0.5))
        source_atom_index = mention.get("source_atom_index")
        identity_key = (str(mention_type), norm_text)

        # --- REJECT: trivial or empty ---
        if len(norm_text.strip()) < 2 or confidence < 0.3:
            entity_decisions.append({
                "mention_text": text,
                "mention_id": mention_id,
                "mention_type": mention_type,
                "normalized_text": norm_text,
                "decision": "REJECT",
                "target_entity_id": None,
                "confidence": confidence,
                "reason": "trivial_text_or_low_confidence",
                "segment_id": segment_id,
                "run_id": run_id,
            })
            continue

        # --- LINK: already seen this normalised form ---
        if identity_key in seen_normalised:
            target_idx = seen_normalised[identity_key]
            target_entity_id = entities[target_idx]["entity_id"]
            entity_decisions.append({
                "mention_text": text,
                "mention_id": mention_id,
                "mention_type": mention_type,
                "normalized_text": norm_text,
                "decision": "LINK",
                "target_entity_id": target_entity_id,
                "confidence": confidence,
                "reason": "matched_normalised_form",
                "segment_id": segment_id,
                "run_id": run_id,
            })
            # Update the target entity
            entities[target_idx]["merged_count"] += 1
            if mention_id not in entities[target_idx]["source_mention_ids"]:
                entities[target_idx]["source_mention_ids"].append(mention_id)
            if text and text not in entities[target_idx]["aliases"]:
                entities[target_idx]["aliases"].append(text)
            if segment_id and segment_id not in entities[target_idx]["segment_ids"]:
                entities[target_idx]["segment_ids"].append(segment_id)
                entities[target_idx]["source_mention_indices"].append(idx)
            if (
                isinstance(source_atom_index, int)
                and source_atom_index not in entities[target_idx]["source_atom_indices"]
            ):
                entities[target_idx]["source_atom_indices"].append(source_atom_index)
            continue

        # --- AMBIGUOUS: check for substring collisions ---
        collision = None
        for (existing_type, existing_norm), ent_idx in seen_normalised.items():
            if existing_type == mention_type and _is_ambiguous_collision(norm_text, existing_norm):
                collision = ent_idx
                break

        if collision is not None:
            entity_decisions.append({
                "mention_text": text,
                "mention_id": mention_id,
                "mention_type": mention_type,
                "normalized_text": norm_text,
                "decision": "AMBIGUOUS",
                "target_entity_id": None,
                "confidence": confidence,
                "reason": f"ambiguous_with_{entities[collision]['entity_id']}",
                "segment_id": segment_id,
                "run_id": run_id,
            })
            continue

        # --- CREATE_CANDIDATE ---
        entity_id = f"ent-{next_entity_num:04d}"
        next_entity_num += 1

        seen_normalised[identity_key] = len(entities)
        entity_decisions.append({
            "mention_text": text,
            "mention_id": mention_id,
            "mention_type": mention_type,
            "normalized_text": norm_text,
            "decision": "CREATE_CANDIDATE",
            "target_entity_id": entity_id,
            "confidence": confidence,
            "reason": "new_entity",
            "segment_id": segment_id,
            "run_id": run_id,
        })
        entities.append({
            "entity_id": entity_id,
            "canonical_text": text,
            "type": mention_type,
            "source_mention_indices": [idx],
            "source_mention_ids": [mention_id],
            "source_atom_indices": (
                [source_atom_index] if isinstance(source_atom_index, int) else []
            ),
            "aliases": [text],
            "merged_count": 1,
            "segment_ids": [segment_id] if segment_id else [],
            "confidence": confidence,
            "document_id": document_id,
            "document_version": document_version,
            "run_id": run_id,
        })

    mention_entity_map = {
        str(item.get("mention_id", "")): str(item.get("target_entity_id", ""))
        for item in entity_decisions
        if item.get("decision") in {"LINK", "CREATE_CANDIDATE"}
        and item.get("mention_id")
        and item.get("target_entity_id")
    }
    return {
        "entities": entities,
        "entity_decisions": entity_decisions,
        "mention_entity_map": mention_entity_map,
    }


# -- helpers ------------------------------------------------------------------


def _atom_to_mention(atom: dict, atom_index: int) -> dict:
    return {
        "mention_id": f"legacy:{atom_index}",
        "text": atom.get("text", ""),
        "normalized_text": atom.get("text", ""),
        "mention_type": atom.get("type", "entity"),
        "segment_id": atom.get("segment_id", ""),
        "evidence": atom.get("evidence", ""),
        "confidence": atom.get("confidence", 0.5),
        "source_atom_index": atom_index,
    }


def _normalize_entity_text(text: str) -> str:
    """Normalise surface form without making semantic merge decisions."""
    normalized = text.strip().casefold()
    # Remove leading articles
    for prefix in ("a ", "an ", "the "):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = ALIAS_MAP.get(normalized, normalized)
    normalized = UNIT_SYNONYM_TABLE.get(normalized, normalized)
    return normalized.casefold()


def _is_ambiguous_collision(a: str, b: str) -> bool:
    """Return True if one string is a substring of the other (potential ambiguity)."""
    if len(a) < 3 or len(b) < 3:
        return False
    return a in b or b in a
