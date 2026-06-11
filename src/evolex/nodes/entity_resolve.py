from __future__ import annotations

import re

from evolex.graph.state import GraphState


def entity_resolve_node(state: GraphState) -> dict:
    """Deduplicate entities across segments and assign canonical names.

    Groups atoms by (normalized_text, type) and designates the highest-confidence
    atom in each group as canonical. Returns a list of resolved entities.
    """
    atoms = state.get("semantic_atoms", [])
    if not atoms:
        return {"entities": []}

    groups: dict[tuple[str, str], list[dict]] = {}
    for idx, atom in enumerate(atoms):
        key = (_normalize_entity_text(atom.get("text", "")), atom.get("type", "claim"))
        groups.setdefault(key, []).append(
            {"index": idx, "text": atom.get("text", ""), "confidence": atom.get("confidence", 0.5), "segment_id": atom.get("segment_id", "")}
        )

    entities: list[dict] = []
    for ent_idx, ((_norm_text, ent_type), entries) in enumerate(groups.items(), start=1):
        canonical = max(entries, key=lambda e: e["confidence"])
        source_indices = [e["index"] for e in entries]
        segment_ids = sorted({e["segment_id"] for e in entries if e["segment_id"]})
        entities.append(
            {
                "entity_id": f"ent-{ent_idx:04d}",
                "canonical_text": canonical["text"],
                "type": ent_type,
                "source_atom_indices": source_indices,
                "merged_count": len(entries),
                "segment_ids": segment_ids,
            }
        )

    return {"entities": entities}


def _normalize_entity_text(text: str) -> str:
    """Normalize entity text for deduplication grouping."""
    normalized = text.strip().lower()
    # Remove common stop-prefixes
    for prefix in ("a ", "an ", "the "):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
