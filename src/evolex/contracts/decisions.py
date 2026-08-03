from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ResolutionDecision = Literal["LINK", "CREATE_CANDIDATE", "AMBIGUOUS", "REJECT"]


@dataclass
class EntityDecision:
    """A decision record produced by the resolver for each mention."""

    mention_text: str
    mention_type: str
    normalized_text: str
    decision: ResolutionDecision
    target_entity_id: str | None = None  # entity_id when LINK
    confidence: float = 0.0
    reason: str = ""
    segment_id: str = ""
    run_id: str = ""


@dataclass
class ResolvedEntity:
    """A resolved entity (the output of successful resolution)."""

    entity_id: str
    canonical_text: str
    entity_type: str
    source_mention_indices: list[int]  # indices into entity_decisions list
    merged_count: int
    segment_ids: list[str]
    confidence: float = 0.0
    document_id: str = ""
    document_version: int = 0
    run_id: str = ""


# -- serialisation helpers ----------------------------------------------------

def entity_decision_to_dict(d: EntityDecision) -> dict:
    return {
        "mention_text": d.mention_text,
        "mention_type": d.mention_type,
        "normalized_text": d.normalized_text,
        "decision": d.decision,
        "target_entity_id": d.target_entity_id,
        "confidence": d.confidence,
        "reason": d.reason,
        "segment_id": d.segment_id,
        "run_id": d.run_id,
    }


def dict_to_entity_decision(d: dict) -> EntityDecision:
    return EntityDecision(
        mention_text=d.get("mention_text", ""),
        mention_type=d.get("mention_type", ""),
        normalized_text=d.get("normalized_text", ""),
        decision=d.get("decision", "CREATE_CANDIDATE"),
        target_entity_id=d.get("target_entity_id"),
        confidence=float(d.get("confidence", 0.0)),
        reason=d.get("reason", ""),
        segment_id=d.get("segment_id", ""),
        run_id=d.get("run_id", ""),
    )


def resolved_entity_to_dict(e: ResolvedEntity) -> dict:
    return {
        "entity_id": e.entity_id,
        "canonical_text": e.canonical_text,
        "entity_type": e.entity_type,
        "source_mention_indices": e.source_mention_indices,
        "merged_count": e.merged_count,
        "segment_ids": e.segment_ids,
        "confidence": e.confidence,
        "document_id": e.document_id,
        "document_version": e.document_version,
        "run_id": e.run_id,
    }


def dict_to_resolved_entity(d: dict) -> ResolvedEntity:
    return ResolvedEntity(
        entity_id=d.get("entity_id", ""),
        canonical_text=d.get("canonical_text", ""),
        entity_type=d.get("entity_type", "entity"),
        source_mention_indices=list(d.get("source_mention_indices", [])),
        merged_count=int(d.get("merged_count", 1)),
        segment_ids=list(d.get("segment_ids", [])),
        confidence=float(d.get("confidence", 0.0)),
        document_id=d.get("document_id", ""),
        document_version=int(d.get("document_version", 0)),
        run_id=d.get("run_id", ""),
    )
