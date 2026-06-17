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
            semantic_atoms: list[dict] = []

            for segment, batch in _map_segments(
                segments,
                lambda segment: extractor.extract_typed(segment["text"]),
                concurrency,
            ):
                for m in batch.get("mentions", []):
                    m.setdefault("segment_id", segment["segment_id"])
                    mentions.append(m)
                for m in batch.get("measurements", []):
                    m.setdefault("segment_id", segment["segment_id"])
                    measurements.append(m)
                for c in batch.get("conditions", []):
                    c.setdefault("segment_id", segment["segment_id"])
                    conditions.append(c)
                for cl in batch.get("claims", []):
                    cl.setdefault("segment_id", segment["segment_id"])
                    claim_candidates.append(cl)
                for ev in batch.get("evidence_spans", []):
                    ev.setdefault("segment_id", segment["segment_id"])
                    evidence_spans.append(ev)
                semantic_atoms.extend(_typed_batch_to_atoms(batch, segment["segment_id"]))

                if extractor.uses_llm:
                    llm_call_count += 1

            result["semantic_atoms"] = semantic_atoms
            result["mentions"] = mentions
            result["measurements"] = measurements
            result["conditions"] = conditions
            result["claim_candidates"] = claim_candidates
            result["evidence_spans"] = evidence_spans
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
