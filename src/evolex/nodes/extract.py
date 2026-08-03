from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from evolex.agents.deepseek_client import BaseExtractor, TypedExtractor
from evolex.graph.state import GraphState


def make_extract_node(extractor: BaseExtractor):
    """Create an extract node that dispatches atoms to typed fields.

    When the extractor is a TypedExtractor the output is split into
    mentions, measurements, conditions, claim_candidates and evidence_spans.
    Otherwise the legacy semantic_atoms list is used.
    """

    def extract_node(state: GraphState) -> dict:
        llm_call_count = state.get("llm_call_count", 0)
        result: dict = {}
        segments = list(state.get("segments", []))
        concurrency = _extract_concurrency(extractor)

        if isinstance(extractor, TypedExtractor):
            mentions: list[dict] = []
            measurements: list[dict] = []
            conditions: list[dict] = []
            claim_candidates: list[dict] = []
            evidence_spans: list[dict] = []
            relation_candidates: list[dict] = []
            semantic_atoms: list[dict] = []

            for segment, raw_batch in _map_segments(
                segments,
                lambda segment: extractor.extract_typed(segment["text"]),
                concurrency,
            ):
                batch = _namespace_typed_batch(raw_batch, segment, state)
                for m in batch.get("mentions", []):
                    mentions.append(m)
                for m in batch.get("measurements", []):
                    measurements.append(m)
                for c in batch.get("conditions", []):
                    conditions.append(c)
                for cl in batch.get("claims", []):
                    claim_candidates.append(cl)
                for ev in batch.get("evidence_spans", []):
                    evidence_spans.append(ev)
                relation_candidates.extend(batch.get("relation_candidates", []))
                semantic_atoms.extend(_typed_batch_to_atoms(batch, segment["segment_id"]))

                if extractor.uses_llm:
                    llm_call_count += 1

            result["semantic_atoms"] = semantic_atoms
            result["mentions"] = mentions
            result["measurements"] = measurements
            result["conditions"] = conditions
            result["claim_candidates"] = claim_candidates
            result["evidence_spans"] = evidence_spans
            result["relation_candidates"] = relation_candidates
        else:
            # Legacy path – plain semantic atoms
            semantic_atoms: list[dict] = []
            for segment, atoms in _map_segments(
                segments,
                lambda segment: extractor.extract(segment["text"]),
                concurrency,
            ):
                for atom in atoms:
                    atom.setdefault("segment_id", segment["segment_id"])
                    atom.setdefault("kg_language", "en")
                    semantic_atoms.append(atom)
                if extractor.uses_llm:
                    llm_call_count += 1
            result["semantic_atoms"] = semantic_atoms

        result["llm_call_count"] = llm_call_count
        return result

    return extract_node


def _extract_concurrency(extractor: BaseExtractor) -> int:
    if not extractor.uses_llm:
        return 1
    config = getattr(extractor, "config", None)
    value = getattr(config, "concurrency", getattr(extractor, "concurrency", 1))
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _map_segments(segments: list[dict], func, concurrency: int):
    if concurrency <= 1 or len(segments) <= 1:
        return [(segment, func(segment)) for segment in segments]

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        values = list(executor.map(func, segments))
    return list(zip(segments, values, strict=False))


def _typed_batch_to_atoms(batch: dict, segment_id: str) -> list[dict]:
    atoms: list[dict] = []

    for mention in batch.get("mentions", []):
        # Preserve the exact atom index on the mention so a later document-level
        # recall-repair pass can map contextual atoms back to canonical entities.
        mention["source_atom_index"] = len(atoms)
        atoms.append(
            {
                "type": mention.get("mention_type", "entity"),
                "text": mention.get("text", ""),
                "evidence": mention.get("evidence", ""),
                "confidence": mention.get("confidence", 0.7),
                "segment_id": segment_id,
                "kg_language": "en",
            }
        )

    for measurement in batch.get("measurements", []):
        atoms.append(
            {
                "type": "measurement",
                "text": measurement.get("text", ""),
                "evidence": measurement.get("evidence", ""),
                "confidence": measurement.get("confidence", 0.7),
                "segment_id": segment_id,
                "kg_language": "en",
            }
        )

    for claim in batch.get("claims", []):
        atoms.append(
            {
                "type": "claim",
                "text": f"{claim.get('subject', '')} {claim.get('predicate', '')} {claim.get('object', '')}".strip(),
                "evidence": str(claim.get("evidence_ids", [])),
                "confidence": claim.get("confidence", 0.5),
                "segment_id": segment_id,
                "kg_language": "en",
            }
        )

    return atoms


def _namespace_typed_batch(
    batch: dict,
    segment: dict,
    state: GraphState,
) -> dict:
    """Make segment-local extraction IDs globally unique within the run."""
    segment_id = str(segment["segment_id"])
    document_id = str(state.get("document_id", ""))
    run_id = str(state.get("run_id", ""))
    source_start = int(segment.get("source_start", 0))

    namespaced: dict[str, list[dict]] = {
        "mentions": [],
        "measurements": [],
        "conditions": [],
        "claims": [],
        "evidence_spans": [],
        "relation_candidates": [],
    }
    mention_id_map: dict[str, str] = {}
    for index, raw in enumerate(batch.get("mentions", []), start=1):
        item = dict(raw)
        local_id = str(item.get("mention_id", f"m{index}"))
        global_id = f"{segment_id}:{local_id}"
        mention_id_map[local_id] = global_id
        item["mention_id"] = global_id
        item["segment_id"] = segment_id
        namespaced["mentions"].append(item)

    evidence_id_map: dict[str, str] = {}
    for index, raw in enumerate(batch.get("evidence_spans", []), start=1):
        item = dict(raw)
        local_id = str(item.get("evidence_id", f"ev-{index:04d}"))
        global_id = f"{segment_id}:{local_id}"
        evidence_id_map[local_id] = global_id
        item["evidence_id"] = global_id
        item["segment_id"] = segment_id
        item["document_id"] = document_id
        item["run_id"] = run_id
        local_span_start = int(item.get("span_start", 0))
        local_span_end = int(item.get("span_end", local_span_start))
        item["segment_span_start"] = local_span_start
        item["segment_span_end"] = local_span_end
        item["span_start"] = source_start + local_span_start
        item["span_end"] = source_start + local_span_end
        namespaced["evidence_spans"].append(item)

    for raw in batch.get("measurements", []):
        item = dict(raw)
        item["segment_id"] = segment_id
        namespaced["measurements"].append(item)

    for raw in batch.get("conditions", []):
        item = dict(raw)
        item["segment_id"] = segment_id
        namespaced["conditions"].append(item)

    for index, raw in enumerate(batch.get("claims", []), start=1):
        item = dict(raw)
        local_id = str(item.get("claim_id", "")).strip() or f"clm-{index:04d}"
        item["claim_id"] = f"{segment_id}:{local_id}"
        item["segment_id"] = segment_id
        item["document_id"] = document_id
        item["document_version"] = int(state.get("document_version", 0))
        item["schema_version"] = str(state.get("schema_version", ""))
        item["run_id"] = run_id
        item["evidence_ids"] = [
            evidence_id_map.get(str(value), str(value))
            for value in item.get("evidence_ids", [])
        ]
        namespaced["claims"].append(item)

    for index, raw in enumerate(batch.get("relation_candidates", []), start=1):
        item = dict(raw)
        local_id = str(item.get("relation_candidate_id", f"rc-{index:04d}"))
        item["relation_candidate_id"] = f"{segment_id}:{local_id}"
        item["subject_mention_id"] = mention_id_map.get(
            str(item.get("subject_mention_id", "")),
            str(item.get("subject_mention_id", "")),
        )
        item["object_mention_id"] = mention_id_map.get(
            str(item.get("object_mention_id", "")),
            str(item.get("object_mention_id", "")),
        )
        item["evidence_ids"] = [
            evidence_id_map.get(str(value), str(value))
            for value in item.get("evidence_ids", [])
        ]
        item["segment_id"] = segment_id
        item["document_id"] = document_id
        item["run_id"] = run_id
        namespaced["relation_candidates"].append(item)

    return namespaced
