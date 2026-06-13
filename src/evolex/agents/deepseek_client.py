from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
ModelLogCallback = Callable[[str, str], None]


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = DEEPSEEK_BASE_URL
    model: str = DEEPSEEK_MODEL
    api_key: str | None = None
    timeout_seconds: int = 30

    def resolved_api_key(self) -> str | None:
        return self.api_key or os.environ.get("DEEPSEEK_API_KEY")


class BaseExtractor(ABC):
    uses_llm = False
    supports_relation_extraction = False

    @abstractmethod
    def extract(self, segment_text: str) -> list[dict]:
        raise NotImplementedError

    def extract_relations(self, atoms: list[dict], entities: list[dict]) -> list[dict]:
        raise NotImplementedError


class TypedExtractor(BaseExtractor):
    """Extractor that produces typed objects (claims, evidence, mentions …).

    Subclasses implement *either* the legacy ``extract()`` method
    *or* the new ``extract_typed()`` method.
    """

    def extract(self, segment_text: str) -> list[dict]:
        """Fallback: convert typed output to legacy atoms."""
        batch = self.extract_typed(segment_text)
        atoms: list[dict] = []
        for claim in batch.get("claims", []):
            atoms.append({
                "type": "claim",
                "text": f"{claim.get('subject', '')} {claim.get('predicate', '')} {claim.get('object', '')}",
                "evidence": str(claim.get("evidence_ids", [])),
                "confidence": claim.get("confidence", 0.5),
            })
        for m in batch.get("measurements", []):
            atoms.append({
                "type": "measurement",
                "text": f"{m.get('parameter', '')}={m.get('value', '')}{m.get('unit', '')}",
                "evidence": m.get("evidence", ""),
                "confidence": m.get("confidence", 0.7),
            })
        return atoms

    def extract_typed(self, segment_text: str) -> dict[str, list[dict]]:
        """Return a batch dict with keys: mentions, measurements, conditions, claims, evidence_spans."""
        raise NotImplementedError


class HeuristicExtractor(BaseExtractor):
    """Stable no-network extractor for explicit offline tests and debug runs."""

    uses_llm = False

    def extract(self, segment_text: str) -> list[dict]:
        atoms: list[dict] = []
        lowered = segment_text.lower()

        for match in re.finditer(r"\b[A-Z][A-Za-z0-9_-]{1,}\b", segment_text):
            atoms.append(_atom("entity", match.group(0), segment_text, 0.72))

        for pattern in (
            r"\b\d+(?:\.\d+)?\s?(?:ms|s|sec|seconds|%|C|°C|K|V|A|ohm|Ω|MB|GB|TB|QPS|RPS)\b",
        ):
            for match in re.finditer(pattern, segment_text, flags=re.IGNORECASE):
                atoms.append(_atom("measurement", match.group(0), segment_text, 0.7))

        for phrase in (
            "latency",
            "throughput",
            "retry",
            "timeout",
            "schema",
            "version",
            "deployment",
            "error rate",
            "breakdown voltage",
            "on-resistance",
        ):
            if phrase.lower() in lowered:
                atoms.append(_atom("property", phrase, segment_text, 0.68))

        if not atoms:
            atoms.append(_atom("claim", "unclassified technical claim", segment_text, 0.55))

        return atoms


class HeuristicTypedExtractor(TypedExtractor):
    """No-network typed extractor that simulates Claim/Evidence output.

    Used only in explicit offline smoke tests and debug runs.
    """

    uses_llm = False
    supports_relation_extraction = False

    def extract_typed(self, segment_text: str) -> dict[str, list[dict]]:
        lowered = segment_text.lower()
        claims: list[dict] = []
        measurements: list[dict] = []
        mentions: list[dict] = []
        evidence_spans: list[dict] = []

        # Minimal measurement detection (numbers with units)
        for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s?(ms|s|%|mTorr|°C|K|V|A|µm/min)\b", segment_text, flags=re.IGNORECASE):
            val_str, unit = match.groups()
            measurements.append({
                "parameter": _infer_parameter(unit),
                "value": float(val_str),
                "unit": unit,
                "text": match.group(0),
                "segment_id": "",
                "evidence": segment_text,
                "confidence": 0.7,
            })

        # Acronyms as mentions
        for match in re.finditer(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", segment_text):
            txt = match.group(0)
            mentions.append({
                "text": txt,
                "normalized_text": txt.lower(),
                "mention_type": "entity",
                "segment_id": "",
                "evidence": segment_text,
                "confidence": 0.72,
            })

        # Generate one claim if there are mentions
        if mentions and measurements:
            claims.append({
                "claim_id": "",
                "subject": mentions[0]["text"],
                "predicate": "has_measurement",
                "object": measurements[0]["parameter"],
                "conditions": [],
                "evidence_ids": [],
                "measurements": [measurements[0]],
                "confidence": 0.6,
                "document_id": "",
                "document_version": 0,
                "schema_version": "",
                "run_id": "",
            })
            # Link claim to evidence
            evidence_spans.append({
                "evidence_id": f"ev-{len(evidence_spans)+1:04d}",
                "document_id": "",
                "segment_id": "",
                "text": segment_text[:200],
                "span_start": 0,
                "span_end": min(len(segment_text), 200),
                "run_id": "",
            })
            # Wire evidence_ids
            claims[-1]["evidence_ids"] = [evidence_spans[-1]["evidence_id"]]

        # Fallback: if we have measurements but no claims, create one
        if not claims and measurements:
            claims.append({
                "claim_id": "",
                "subject": "system",
                "predicate": "has_measurement",
                "object": measurements[0]["parameter"],
                "conditions": [],
                "evidence_ids": [],
                "measurements": [measurements[0]],
                "confidence": 0.55,
                "document_id": "",
                "document_version": 0,
                "schema_version": "",
                "run_id": "",
            })
            evidence_spans.append({
                "evidence_id": "ev-0001",
                "document_id": "",
                "segment_id": "",
                "text": segment_text[:200],
                "span_start": 0,
                "span_end": min(len(segment_text), 200),
                "run_id": "",
            })
            claims[-1]["evidence_ids"] = ["ev-0001"]

        # Truly empty – produce one fallback claim
        if not claims:
            claims.append({
                "claim_id": "",
                "subject": "system",
                "predicate": "related_to",
                "object": "unclassified concept",
                "conditions": [],
                "evidence_ids": [],
                "measurements": [],
                "confidence": 0.55,
                "document_id": "",
                "document_version": 0,
                "schema_version": "",
                "run_id": "",
            })
            evidence_spans.append({
                "evidence_id": "ev-0001",
                "document_id": "",
                "segment_id": "",
                "text": segment_text[:200],
                "span_start": 0,
                "span_end": min(len(segment_text), 200),
                "run_id": "",
            })
            claims[-1]["evidence_ids"] = ["ev-0001"]

        return {
            "mentions": mentions,
            "measurements": measurements,
            "conditions": [],
            "claims": claims,
            "evidence_spans": evidence_spans,
        }


def _infer_parameter(unit: str) -> str:
    unit_lower = unit.lower().replace("°", "")
    if unit_lower in ("ms", "s", "sec", "seconds"):
        return "time"
    if unit_lower in ("%",):
        return "percentage"
    if unit_lower in ("mtorr",):
        return "pressure"
    if unit_lower in ("c",):
        return "temperature"
    if unit_lower in ("v",):
        return "voltage"
    if unit_lower in ("a",):
        return "current"
    if unit_lower in ("µm/min", "um/min"):
        return "rate"
    return "measurement"


class DeepSeekExtractor(TypedExtractor):
    uses_llm = True
    supports_relation_extraction = True

    def __init__(
        self,
        api_key: str,
        base_url: str = DEEPSEEK_BASE_URL,
        model: str = DEEPSEEK_MODEL,
        timeout_seconds: int = 30,
        on_event: ModelLogCallback | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.on_event = on_event
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI SDK is required for DeepSeek API calls. "
                "Install dependencies with `conda env update -f environment.yml --prune`."
            ) from exc
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout_seconds)

    def extract(self, segment_text: str) -> list[dict]:
        self._emit("llm", f"Semantic extraction request started. chars={len(segment_text)}")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a technical document semantic extractor. "
                            "Return only a JSON array. Each item must contain type, text, "
                            "evidence, and confidence. The KG-facing fields type and text "
                            "must be in English. Use evidence for the original source span. "
                            "Do not output Markdown."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Extract Phase 1 semantic atoms from this segment:\n{segment_text}",
                    },
                ],
                stream=False,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}},
            )
        except Exception as exc:
            raise RuntimeError(
                f"DeepSeek API request failed: {_sanitize_error_message(str(exc))}"
            ) from exc

        content = response.choices[0].message.content or ""
        self._emit("llm", f"Semantic extraction model output: {_truncate_log(content)}")
        atoms = _parse_json_atoms(content)
        normalized_atoms = [_normalize_atom(atom, segment_text) for atom in atoms]
        self._emit("llm", f"Semantic extraction parsed {len(normalized_atoms)} atoms.")
        return normalized_atoms

    def extract_typed(self, segment_text: str) -> dict[str, list[dict]]:
        """Convert the legacy atom response into typed Phase 3 objects.

        This keeps the public "system" pipeline usable while the model prompt
        still emits the older Phase 1 atom schema.
        """
        atoms = self.extract(segment_text)
        return _atoms_to_typed_batch(atoms, segment_text)

    def extract_relations(self, atoms: list[dict], entities: list[dict]) -> list[dict]:
        self._emit(
            "llm",
            f"Relation extraction request started. atoms={len(atoms)} entities={len(entities)}",
        )
        atom_entity_map: dict[int, str] = {}
        for entity in entities:
            for atom_index in entity.get("source_atom_indices", []):
                atom_entity_map[atom_index] = entity["entity_id"]

        atom_lines = []
        for index, atom in enumerate(atoms):
            atom_lines.append(
                f"[{index}] type={atom.get('type')}, text={atom.get('text')!r}, "
                f"entity={atom_entity_map.get(index, 'none')}, "
                f"segment={atom.get('segment_id', '')}"
            )

        entity_lines = [
            f"{entity['entity_id']}: {entity.get('canonical_text')} ({entity.get('type')})"
            for entity in entities
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a technical knowledge-graph relation extractor. "
                            "Return only a JSON array. Each item must contain "
                            "subject_entity_id, predicate, object_entity_id, evidence, "
                            "and confidence. Use only entity IDs from the provided list. "
                            "Use concise English snake_case predicates. Do not output Markdown."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Entities:\n"
                            + "\n".join(entity_lines)
                            + "\n\nAtoms:\n"
                            + "\n".join(atom_lines)
                        ),
                    },
                ],
                stream=False,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}},
            )
        except Exception as exc:
            raise RuntimeError(
                f"DeepSeek relation extraction failed: {_sanitize_error_message(str(exc))}"
            ) from exc

        content = response.choices[0].message.content or ""
        self._emit("llm", f"Relation extraction model output: {_truncate_log(content)}")
        relations = _parse_json_relations(content)
        entity_ids = {entity["entity_id"] for entity in entities}
        normalized_relations = [
            _normalize_relation(relation, index, entity_ids)
            for index, relation in enumerate(relations, start=1)
        ]
        self._emit("llm", f"Relation extraction parsed {len(normalized_relations)} relations.")
        return normalized_relations

    def _emit(self, stage: str, message: str) -> None:
        if self.on_event is not None:
            self.on_event(stage, message)


def get_default_extractor(
    on_event: ModelLogCallback | None = None,
    *,
    typed: bool = False,
    llm_config: LLMConfig | None = None,
) -> BaseExtractor:
    if os.environ.get("EVOLEX_OFFLINE") == "1":
        return HeuristicTypedExtractor() if typed else HeuristicExtractor()

    config = llm_config or LLMConfig()
    api_key = config.resolved_api_key()
    if api_key:
        return DeepSeekExtractor(
            api_key=api_key,
            base_url=config.base_url,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            on_event=on_event,
        )
    raise RuntimeError(
        "LLM API key is required. Set it with `set llm api-key ...` in the CLI, "
        "pass `--llm-api-key`, export DEEPSEEK_API_KEY, or set EVOLEX_OFFLINE=1 "
        "for explicit local debug mode."
    )


def _atoms_to_typed_batch(atoms: list[dict[str, Any]], segment_text: str) -> dict[str, list[dict]]:
    mentions: list[dict] = []
    measurements: list[dict] = []
    conditions: list[dict] = []
    claims: list[dict] = []
    evidence_spans: list[dict] = []

    def add_evidence(text: str) -> str:
        evidence_id = f"ev-{len(evidence_spans) + 1:04d}"
        evidence_spans.append(
            {
                "evidence_id": evidence_id,
                "document_id": "",
                "segment_id": "",
                "text": text[:200],
                "span_start": 0,
                "span_end": min(len(text), 200),
                "run_id": "",
            }
        )
        return evidence_id

    mention_types = {"entity", "process", "material", "tool", "property"}

    for atom in atoms:
        atom_type = atom.get("type", "claim")
        atom_text = str(atom.get("text", "")).strip()
        atom_evidence = str(atom.get("evidence", segment_text)) or segment_text
        confidence = atom.get("confidence", 0.5)

        if atom_type in mention_types and atom_text:
            mentions.append(
                {
                    "text": atom_text,
                    "normalized_text": atom_text.lower(),
                    "mention_type": "entity" if atom_type == "property" else atom_type,
                    "segment_id": "",
                    "evidence": atom_evidence,
                    "confidence": confidence,
                }
            )

        if atom_type == "measurement":
            measurement = _measurement_from_text(atom_text, atom_evidence, confidence)
            if measurement is not None:
                measurements.append(measurement)

    primary_subject = mentions[0]["text"] if mentions else "system"

    for atom in atoms:
        atom_type = atom.get("type", "claim")
        atom_text = str(atom.get("text", "")).strip()
        atom_evidence = str(atom.get("evidence", segment_text)) or segment_text
        confidence = atom.get("confidence", 0.5)
        evidence_id = add_evidence(atom_evidence)

        if atom_type == "measurement":
            linked_measurement = _measurement_from_text(atom_text, atom_evidence, confidence)
            if linked_measurement is None:
                continue
            claims.append(
                {
                    "claim_id": "",
                    "subject": primary_subject,
                    "predicate": "has_measurement",
                    "object": linked_measurement["parameter"],
                    "conditions": [],
                    "evidence_ids": [evidence_id],
                    "measurements": [linked_measurement],
                    "confidence": confidence,
                    "document_id": "",
                    "document_version": 0,
                    "schema_version": "",
                    "run_id": "",
                }
            )
            continue

        if atom_type == "property" and atom_text:
            claims.append(
                {
                    "claim_id": "",
                    "subject": primary_subject,
                    "predicate": "has_property",
                    "object": atom_text,
                    "conditions": [],
                    "evidence_ids": [evidence_id],
                    "measurements": [],
                    "confidence": confidence,
                    "document_id": "",
                    "document_version": 0,
                    "schema_version": "",
                    "run_id": "",
                }
            )
            continue

        if atom_type == "claim" and atom_text:
            claims.append(
                {
                    "claim_id": "",
                    "subject": primary_subject,
                    "predicate": "related_to",
                    "object": atom_text,
                    "conditions": [],
                    "evidence_ids": [evidence_id],
                    "measurements": [],
                    "confidence": confidence,
                    "document_id": "",
                    "document_version": 0,
                    "schema_version": "",
                    "run_id": "",
                }
            )

    if not claims:
        evidence_id = add_evidence(segment_text)
        claims.append(
            {
                "claim_id": "",
                "subject": primary_subject,
                "predicate": "related_to",
                "object": "unclassified concept",
                "conditions": [],
                "evidence_ids": [evidence_id],
                "measurements": measurements[:1],
                "confidence": 0.55,
                "document_id": "",
                "document_version": 0,
                "schema_version": "",
                "run_id": "",
            }
        )

    return {
        "mentions": mentions,
        "measurements": measurements,
        "conditions": conditions,
        "claims": claims,
        "evidence_spans": evidence_spans,
    }


def _measurement_from_text(text: str, evidence: str, confidence: float) -> dict[str, Any] | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s?(ms|s|sec|seconds|%|mTorr|°C|C|K|V|A|µm/min|um/min)\b", text, flags=re.IGNORECASE)
    if match is None:
        return None
    value, unit = match.groups()
    return {
        "parameter": _infer_parameter(unit),
        "value": float(value),
        "unit": unit,
        "text": text[:200],
        "segment_id": "",
        "evidence": evidence[:500],
        "confidence": confidence,
    }


def _parse_json_atoms(content: str) -> list[dict[str, Any]]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, list):
        raise ValueError("DeepSeek extractor response must be a JSON array")
    return [item for item in parsed if isinstance(item, dict)]


def _parse_json_relations(content: str) -> list[dict[str, Any]]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, list):
        raise ValueError("DeepSeek relation response must be a JSON array")
    return [item for item in parsed if isinstance(item, dict)]


def _normalize_atom(atom: dict[str, Any], fallback_evidence: str) -> dict:
    return {
        "type": _normalize_type(str(atom.get("type", "claim"))),
        "text": _ascii_or_default(str(atom.get("text", "")), "unclassified technical claim")[
            :200
        ],
        "evidence": str(atom.get("evidence", fallback_evidence))[:500],
        "confidence": _safe_confidence(atom.get("confidence", 0.5)),
        "kg_language": "en",
    }


def _normalize_relation(relation: dict[str, Any], index: int, entity_ids: set[str]) -> dict:
    subject = str(relation.get("subject_entity_id", ""))
    obj = str(relation.get("object_entity_id", ""))
    if subject not in entity_ids or obj not in entity_ids:
        raise ValueError("DeepSeek relation response referenced an unknown entity_id")

    predicate = _normalize_type(str(relation.get("predicate", "related_to")))
    return {
        "relation_id": f"rel-{index:04d}",
        "subject_entity_id": subject,
        "predicate": predicate or "related_to",
        "object_entity_id": obj,
        "evidence": str(relation.get("evidence", ""))[:500],
        "confidence": _safe_confidence(relation.get("confidence", 0.5)),
    }


def _safe_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, confidence))


def _atom(atom_type: str, text: str, evidence: str, confidence: float) -> dict:
    return {
        "type": atom_type,
        "text": text,
        "evidence": evidence,
        "confidence": confidence,
        "kg_language": "en",
    }


def _ascii_or_default(value: str, default: str) -> str:
    if value and value.isascii():
        return value
    return default


def _normalize_type(value: str) -> str:
    if not value or not value.isascii():
        return "claim"
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    return normalized or "claim"


def _sanitize_error_message(message: str) -> str:
    message = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer [redacted]", message)
    return message[:500]


def _truncate_log(value: str, limit: int = 500) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."
