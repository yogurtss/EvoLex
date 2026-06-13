from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Evidence – the lowest-level span-level anchor.
# ---------------------------------------------------------------------------


@dataclass
class Evidence:
    """A single text span that supports a claim."""

    evidence_id: str
    document_id: str
    segment_id: str
    text: str
    span_start: int
    span_end: int
    run_id: str


# ---------------------------------------------------------------------------
# Condition – parameterised environment / constraint on a Claim.
# ---------------------------------------------------------------------------


@dataclass
class Condition:
    """A named condition (parameter + optional value/unit) attached to a Claim."""

    parameter: str
    value: float | str | None = None
    unit: str = ""


# ---------------------------------------------------------------------------
# Measurement – a quantitative observation with a unit.
# ---------------------------------------------------------------------------


@dataclass
class Measurement:
    """A single numeric measurement extracted from text."""

    parameter: str
    value: float
    unit: str
    text: str
    segment_id: str
    evidence: str
    confidence: float = 0.7


# ---------------------------------------------------------------------------
# Mention – a raw text reference that may become an Entity later.
# ---------------------------------------------------------------------------


@dataclass
class Mention:
    """An entity mention before resolution."""

    text: str
    normalized_text: str
    mention_type: str  # e.g. "entity", "process", "material", "tool"
    segment_id: str
    evidence: str
    confidence: float = 0.7


# ---------------------------------------------------------------------------
# Claim – the central knowledge unit.
# ---------------------------------------------------------------------------
_CLAIM_COUNTER: dict[str, int] = {}


def _next_claim_id() -> str:
    _CLAIM_COUNTER["n"] = _CLAIM_COUNTER.get("n", 0) + 1
    return f"clm-{_CLAIM_COUNTER['n']:04d}"


@dataclass
class Claim:
    """A structured claim with subject-predicate-object and evidence linkage.

    Every Claim MUST have at least one evidence_id.
    """

    claim_id: str = field(default_factory=_next_claim_id)
    subject: str = ""
    predicate: str = ""
    object: str = ""
    conditions: list[Condition] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    confidence: float = 0.5
    document_id: str = ""
    document_version: int = 0
    schema_version: str = ""
    run_id: str = ""


# ---------------------------------------------------------------------------
# Serialisation helpers  (dict ↔ dataclass)
# ---------------------------------------------------------------------------

_EVIDENCE_KEYS = {"evidence_id", "document_id", "segment_id", "text", "span_start", "span_end", "run_id"}
_CONDITION_KEYS = {"parameter", "value", "unit"}
_MEASUREMENT_KEYS = {"parameter", "value", "unit", "text", "segment_id", "evidence", "confidence"}
_MENTION_KEYS = {"text", "normalized_text", "mention_type", "segment_id", "evidence", "confidence"}
_CLAIM_KEYS = {"claim_id", "subject", "predicate", "object", "conditions", "evidence_ids",
               "measurements", "confidence", "document_id", "document_version", "schema_version", "run_id"}


def dict_to_evidence(d: dict[str, Any]) -> Evidence:
    keys = _EVIDENCE_KEYS
    missing = keys - set(d)
    if missing:
        raise ValueError(f"Evidence missing fields: {sorted(missing)}")
    return Evidence(
        evidence_id=d["evidence_id"],
        document_id=d["document_id"],
        segment_id=d["segment_id"],
        text=d["text"],
        span_start=d["span_start"],
        span_end=d["span_end"],
        run_id=d["run_id"],
    )


def evidence_to_dict(ev: Evidence) -> dict[str, Any]:
    return {
        "evidence_id": ev.evidence_id,
        "document_id": ev.document_id,
        "segment_id": ev.segment_id,
        "text": ev.text,
        "span_start": ev.span_start,
        "span_end": ev.span_end,
        "run_id": ev.run_id,
    }


def dict_to_condition(d: dict[str, Any]) -> Condition:
    return Condition(
        parameter=d.get("parameter", ""),
        value=d.get("value"),
        unit=d.get("unit", ""),
    )


def condition_to_dict(c: Condition) -> dict[str, Any]:
    return {"parameter": c.parameter, "value": c.value, "unit": c.unit}


def dict_to_measurement(d: dict[str, Any]) -> Measurement:
    missing = _MEASUREMENT_KEYS - set(d)
    if missing:
        raise ValueError(f"Measurement missing fields: {sorted(missing)}")
    return Measurement(
        parameter=d["parameter"],
        value=float(d["value"]),
        unit=d["unit"],
        text=d["text"],
        segment_id=d["segment_id"],
        evidence=d["evidence"],
        confidence=float(d.get("confidence", 0.7)),
    )


def measurement_to_dict(m: Measurement) -> dict[str, Any]:
    return {
        "parameter": m.parameter,
        "value": m.value,
        "unit": m.unit,
        "text": m.text,
        "segment_id": m.segment_id,
        "evidence": m.evidence,
        "confidence": m.confidence,
    }


def dict_to_mention(d: dict[str, Any]) -> Mention:
    missing = _MENTION_KEYS - set(d)
    if missing:
        raise ValueError(f"Mention missing fields: {sorted(missing)}")
    return Mention(
        text=d["text"],
        normalized_text=d["normalized_text"],
        mention_type=d["mention_type"],
        segment_id=d["segment_id"],
        evidence=d["evidence"],
        confidence=float(d.get("confidence", 0.7)),
    )


def mention_to_dict(m: Mention) -> dict[str, Any]:
    return {
        "text": m.text,
        "normalized_text": m.normalized_text,
        "mention_type": m.mention_type,
        "segment_id": m.segment_id,
        "evidence": m.evidence,
        "confidence": m.confidence,
    }


def dict_to_claim(d: dict[str, Any]) -> Claim:
    missing = _CLAIM_KEYS - set(d)
    if missing:
        raise ValueError(f"Claim missing fields: {sorted(missing)}")
    conditions = [dict_to_condition(c) for c in d.get("conditions", [])]
    measurements = [dict_to_measurement(m) for m in d.get("measurements", [])]
    return Claim(
        claim_id=d.get("claim_id", _next_claim_id()),
        subject=d["subject"],
        predicate=d["predicate"],
        object=d["object"],
        conditions=conditions,
        evidence_ids=list(d.get("evidence_ids", [])),
        measurements=measurements,
        confidence=float(d.get("confidence", 0.5)),
        document_id=d.get("document_id", ""),
        document_version=int(d.get("document_version", 0)),
        schema_version=d.get("schema_version", ""),
        run_id=d.get("run_id", ""),
    )


def claim_to_dict(c: Claim) -> dict[str, Any]:
    return {
        "claim_id": c.claim_id,
        "subject": c.subject,
        "predicate": c.predicate,
        "object": c.object,
        "conditions": [condition_to_dict(cnd) for cnd in c.conditions],
        "evidence_ids": c.evidence_ids,
        "measurements": [measurement_to_dict(m) for m in c.measurements],
        "confidence": c.confidence,
        "document_id": c.document_id,
        "document_version": c.document_version,
        "schema_version": c.schema_version,
        "run_id": c.run_id,
    }
