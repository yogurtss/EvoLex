from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
LOCAL_API_KEY = "local-openai-compatible"
ModelLogCallback = Callable[[str, str], None]


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = DEEPSEEK_BASE_URL
    model: str = DEEPSEEK_MODEL
    api_key: str | None = None
    timeout_seconds: int = 30
    concurrency: int = 4
    profile: str | None = None

    def resolved_api_key(self) -> str | None:
        return self.api_key or os.environ.get("EVOLEX_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")

    def api_key_source(self) -> str:
        if self.api_key:
            return "configured via CLI"
        if os.environ.get("EVOLEX_API_KEY"):
            return "configured via EVOLEX_API_KEY"
        if os.environ.get("DEEPSEEK_API_KEY"):
            return "configured via DEEPSEEK_API_KEY"
        if self.allows_local_keyless():
            return "not configured; local/generic key optional"
        return "not configured; runs require a key unless EVOLEX_OFFLINE=1"

    def inferred_profile(self) -> str:
        if self.profile:
            return self.profile.strip().lower()
        base_url = self.base_url.lower()
        model = self.model.lower()
        if "deepseek" in base_url or model.startswith("deepseek"):
            return "deepseek"
        return "generic"

    def allows_local_keyless(self) -> bool:
        if self.inferred_profile() == "deepseek":
            return False
        host = (urlparse(self.base_url).hostname or "").lower()
        return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

    def effective_api_key(self) -> str | None:
        key = self.resolved_api_key()
        if key:
            return key
        if self.allows_local_keyless():
            return LOCAL_API_KEY
        return None


def chat_completion_kwargs(
    config: LLMConfig,
    messages: list[dict[str, str]],
    *,
    reasoning_effort: str | None = None,
    thinking_type: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "stream": False,
    }
    if config.inferred_profile() == "deepseek":
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if thinking_type:
            kwargs["extra_body"] = {"thinking": {"type": thinking_type}}
    return kwargs


class BaseExtractor(ABC):
    uses_llm = False
    supports_relation_extraction = False
    supports_joint_extraction = False

    @abstractmethod
    def extract(self, segment_text: str) -> list[dict]:
        raise NotImplementedError

    def extract_relations(self, atoms: list[dict], entities: list[dict]) -> list[dict]:
        raise NotImplementedError


class TypedExtractor(BaseExtractor):
    """Extractor that produces evidence-scoped graph objects in one pass.

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
        """Return mentions, relation candidates, claims, and evidence spans.

        Joint extractors give every mention a segment-local ``mention_id`` and
        make relation endpoints refer to those IDs.  The graph layer namespaces
        the IDs and resolves them to canonical entity IDs later, so a relation
        never depends on a second model call reconstructing lost context.
        """
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
    supports_joint_extraction = True

    def extract_typed(self, segment_text: str) -> dict[str, list[dict]]:
        payload = {
            "mentions": _heuristic_mentions(segment_text),
            "relations": [],
            "measurements": [],
            "conditions": [],
        }

        for match in re.finditer(
            r"\b(\d+(?:\.\d+)?)\s?(ms|s|%|mTorr|°C|K|V|A|µm/min)\b",
            segment_text,
            flags=re.IGNORECASE,
        ):
            value, unit = match.groups()
            measurement_id = f"m{len(payload['mentions']) + 1}"
            payload["mentions"].append(
                {
                    "mention_id": measurement_id,
                    "text": match.group(0),
                    "mention_type": "measurement",
                    "confidence": 0.7,
                    "_start": match.start(),
                    "_end": match.end(),
                }
            )
            payload["measurements"].append(
                {
                    "parameter": _infer_parameter(unit),
                    "value": float(value),
                    "unit": unit,
                    "text": match.group(0),
                    "evidence": segment_text,
                    "confidence": 0.7,
                }
            )

        payload["relations"] = _heuristic_relations(
            segment_text,
            payload["mentions"],
        )
        return _normalize_joint_batch(payload, segment_text)


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


class OpenAICompatibleExtractor(TypedExtractor):
    uses_llm = True
    supports_relation_extraction = True
    supports_joint_extraction = True

    def __init__(
        self,
        api_key: str,
        base_url: str = DEEPSEEK_BASE_URL,
        model: str = DEEPSEEK_MODEL,
        timeout_seconds: int = 30,
        concurrency: int = 4,
        on_event: ModelLogCallback | None = None,
        profile: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.concurrency = max(1, int(concurrency))
        self.on_event = on_event
        self.config = LLMConfig(
            base_url=self.base_url,
            model=self.model,
            api_key=self.api_key,
            timeout_seconds=self.timeout_seconds,
            concurrency=self.concurrency,
            profile=profile,
        )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI SDK is required for LLM API calls. "
                "Install dependencies with `conda env update -f environment.yml --prune`."
            ) from exc
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout_seconds)

    def extract(self, segment_text: str) -> list[dict]:
        self._emit("llm", f"Semantic extraction request started. chars={len(segment_text)}")
        try:
            response = self.client.chat.completions.create(
                **chat_completion_kwargs(
                    self._active_config(),
                    [
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
                    reasoning_effort="high",
                    thinking_type="enabled",
                )
            )
        except Exception as exc:
            raise RuntimeError(
                f"LLM API request failed: {_sanitize_error_message(str(exc))}"
            ) from exc

        content = response.choices[0].message.content or ""
        self._emit("llm", f"Semantic extraction model output: {_truncate_log(content)}")
        atoms = _parse_json_atoms(content)
        normalized_atoms = [_normalize_atom(atom, segment_text) for atom in atoms]
        self._emit("llm", f"Semantic extraction parsed {len(normalized_atoms)} atoms.")
        return normalized_atoms

    def extract_typed(self, segment_text: str) -> dict[str, list[dict]]:
        """Jointly extract entities and their relations from one source span."""
        self._emit("llm", f"Joint graph extraction request started. chars={len(segment_text)}")
        try:
            response = self.client.chat.completions.create(
                **chat_completion_kwargs(
                    self._active_config(),
                    [
                        {
                            "role": "system",
                            "content": (
                                "You jointly extract a technical knowledge graph from one "
                                "source segment. Return only one JSON object with arrays "
                                "mentions, relations, measurements, and conditions. Each "
                                "mention must contain mention_id, text, mention_type, and "
                                "confidence. Each relation must contain subject_mention_id, "
                                "predicate, object_mention_id, evidence, and confidence. "
                                "Relation endpoints must use mention_id values declared in "
                                "the same response. Include literal values as mentions when "
                                "they are relation endpoints. Use concise English canonical "
                                "text and snake_case predicates, while evidence must be an "
                                "exact source span. Do not output Markdown or infer facts "
                                "that are not stated in the segment."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                "Jointly extract entity mentions and relations from this "
                                f"technical segment:\n{segment_text}"
                            ),
                        },
                    ],
                    reasoning_effort="high",
                    thinking_type="enabled",
                )
            )
        except Exception as exc:
            raise RuntimeError(
                f"LLM joint graph extraction failed: {_sanitize_error_message(str(exc))}"
            ) from exc

        content = response.choices[0].message.content or ""
        self._emit("llm", f"Joint graph extraction model output: {_truncate_log(content)}")
        payload = _parse_json_object(content)
        batch = _normalize_joint_batch(payload, segment_text)
        self._emit(
            "llm",
            "Joint graph extraction parsed "
            f"{len(batch['mentions'])} mentions and "
            f"{len(batch['relation_candidates'])} relations.",
        )
        return batch

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
                **chat_completion_kwargs(
                    self._active_config(),
                    [
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
                    reasoning_effort="high",
                    thinking_type="enabled",
                )
            )
        except Exception as exc:
            raise RuntimeError(
                f"LLM relation extraction failed: {_sanitize_error_message(str(exc))}"
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

    def _active_config(self) -> LLMConfig:
        config = getattr(self, "config", None)
        if isinstance(config, LLMConfig):
            return config
        return LLMConfig(
            base_url=getattr(self, "base_url", DEEPSEEK_BASE_URL),
            model=getattr(self, "model", DEEPSEEK_MODEL),
            api_key=getattr(self, "api_key", None),
            timeout_seconds=getattr(self, "timeout_seconds", 30),
            concurrency=getattr(self, "concurrency", 1),
        )


class DeepSeekExtractor(OpenAICompatibleExtractor):
    """Backward-compatible DeepSeek-named extractor.

    The implementation is OpenAI-compatible; DeepSeek-specific request fields
    are enabled only when the config/profile resolves to ``deepseek``.
    """


def get_default_extractor(
    on_event: ModelLogCallback | None = None,
    *,
    typed: bool = False,
    llm_config: LLMConfig | None = None,
) -> BaseExtractor:
    if os.environ.get("EVOLEX_OFFLINE") == "1":
        return HeuristicTypedExtractor() if typed else HeuristicExtractor()

    config = llm_config or LLMConfig()
    api_key = config.effective_api_key()
    if api_key:
        return DeepSeekExtractor(
            api_key=api_key,
            base_url=config.base_url,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            concurrency=config.concurrency,
            on_event=on_event,
            profile=config.profile,
        )
    raise RuntimeError(
        "LLM API key is required. Set it with `set llm api-key ...` in the CLI, "
        "pass `--llm-api-key`, export EVOLEX_API_KEY or DEEPSEEK_API_KEY, "
        "or set EVOLEX_OFFLINE=1 "
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
        "relation_candidates": [],
        "measurements": measurements,
        "conditions": conditions,
        "claims": claims,
        "evidence_spans": evidence_spans,
    }


def _normalize_joint_batch(
    payload: dict[str, Any],
    segment_text: str,
) -> dict[str, list[dict]]:
    """Validate a joint model response and derive evidence-linked claims.

    The response uses local mention IDs.  Invalid endpoint references are
    excluded instead of being guessed, which makes the later mapping step
    deterministic and auditable.
    """
    mentions: list[dict] = []
    local_id_map: dict[str, str] = {}
    mention_text_by_id: dict[str, str] = {}

    raw_mentions = payload.get("mentions", [])
    if not isinstance(raw_mentions, list):
        raw_mentions = []
    for index, raw in enumerate(raw_mentions, start=1):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", "")).strip()[:200]
        if not text:
            continue
        requested_id = str(raw.get("mention_id", f"m{index}")).strip() or f"m{index}"
        mention_id = requested_id
        suffix = 2
        while mention_id in mention_text_by_id:
            mention_id = f"{requested_id}_{suffix}"
            suffix += 1
        local_id_map.setdefault(requested_id, mention_id)
        mention_text_by_id[mention_id] = text
        mentions.append(
            {
                "mention_id": mention_id,
                "text": text,
                "normalized_text": text.casefold(),
                "mention_type": _normalize_type(
                    str(raw.get("mention_type", raw.get("type", "entity")))
                ),
                "segment_id": "",
                "evidence": str(raw.get("evidence", segment_text))[:500],
                "confidence": _safe_confidence(raw.get("confidence", 0.7)),
            }
        )

    if not mentions:
        mentions.append(
            {
                "mention_id": "m1",
                "text": "system",
                "normalized_text": "system",
                "mention_type": "entity",
                "segment_id": "",
                "evidence": segment_text[:500],
                "confidence": 0.5,
            }
        )
        local_id_map["m1"] = "m1"
        mention_text_by_id["m1"] = "system"

    evidence_spans: list[dict] = []
    relation_candidates: list[dict] = []
    claims: list[dict] = []
    raw_relations = payload.get("relations", payload.get("relation_candidates", []))
    if not isinstance(raw_relations, list):
        raw_relations = []

    for index, raw in enumerate(raw_relations, start=1):
        if not isinstance(raw, dict):
            continue
        raw_subject = str(
            raw.get("subject_mention_id", raw.get("subject_ref", ""))
        ).strip()
        raw_object = str(
            raw.get("object_mention_id", raw.get("object_ref", ""))
        ).strip()
        subject_id = local_id_map.get(raw_subject, raw_subject)
        object_id = local_id_map.get(raw_object, raw_object)
        predicate = _normalize_type(str(raw.get("predicate", "related_to")))
        evidence = str(raw.get("evidence", segment_text)).strip() or segment_text
        if evidence not in segment_text:
            evidence = segment_text
        span_start = segment_text.find(evidence)
        if span_start < 0:
            span_start = 0
        evidence_id = f"ev-{len(evidence_spans) + 1:04d}"
        evidence_spans.append(
            {
                "evidence_id": evidence_id,
                "document_id": "",
                "segment_id": "",
                "text": evidence[:500],
                "span_start": span_start,
                "span_end": min(len(segment_text), span_start + len(evidence)),
                "run_id": "",
            }
        )
        confidence = _safe_confidence(raw.get("confidence", 0.5))
        candidate_id = str(raw.get("relation_candidate_id", f"rc-{index:04d}"))
        endpoints_valid = (
            subject_id in mention_text_by_id
            and object_id in mention_text_by_id
        )
        relation_candidates.append(
            {
                "relation_candidate_id": candidate_id,
                "subject_mention_id": subject_id,
                "predicate": predicate or "related_to",
                "object_mention_id": object_id,
                "evidence": evidence[:500],
                "evidence_ids": [evidence_id],
                "confidence": confidence,
                "segment_id": "",
                "extraction_mode": "joint",
                "endpoint_validation_status": (
                    "valid" if endpoints_valid else "invalid"
                ),
                "endpoint_validation_errors": [
                    label
                    for label, endpoint_id in (
                        ("unknown_subject_mention_id", subject_id),
                        ("unknown_object_mention_id", object_id),
                    )
                    if endpoint_id not in mention_text_by_id
                ],
            }
        )
        if not endpoints_valid:
            continue
        claims.append(
            {
                "claim_id": "",
                "subject": mention_text_by_id[subject_id],
                "predicate": predicate or "related_to",
                "object": mention_text_by_id[object_id],
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

    measurements: list[dict] = []
    raw_measurements = payload.get("measurements", [])
    if isinstance(raw_measurements, list):
        for raw in raw_measurements:
            if not isinstance(raw, dict):
                continue
            try:
                value = float(raw.get("value"))
            except (TypeError, ValueError):
                continue
            measurements.append(
                {
                    "parameter": _normalize_type(str(raw.get("parameter", "measurement"))),
                    "value": value,
                    "unit": str(raw.get("unit", ""))[:40],
                    "text": str(raw.get("text", ""))[:200],
                    "segment_id": "",
                    "evidence": str(raw.get("evidence", segment_text))[:500],
                    "confidence": _safe_confidence(raw.get("confidence", 0.7)),
                }
            )

    conditions = [
        dict(item)
        for item in payload.get("conditions", [])
        if isinstance(item, dict)
    ]

    if not claims:
        evidence_id = f"ev-{len(evidence_spans) + 1:04d}"
        evidence_spans.append(
            {
                "evidence_id": evidence_id,
                "document_id": "",
                "segment_id": "",
                "text": segment_text[:500],
                "span_start": 0,
                "span_end": min(len(segment_text), 500),
                "run_id": "",
            }
        )
        claims.append(
            {
                "claim_id": "",
                "subject": mentions[0]["text"],
                "predicate": "related_to",
                "object": "unclassified concept",
                "conditions": [],
                "evidence_ids": [evidence_id],
                "measurements": measurements[:1],
                "confidence": 0.45,
                "document_id": "",
                "document_version": 0,
                "schema_version": "",
                "run_id": "",
            }
        )

    return {
        "mentions": mentions,
        "relation_candidates": relation_candidates,
        "measurements": measurements,
        "conditions": conditions,
        "claims": claims,
        "evidence_spans": evidence_spans,
    }


def _heuristic_mentions(segment_text: str) -> list[dict]:
    """Extract conservative technical name spans for deterministic tests."""
    pattern = re.compile(
        r"\b(?:[A-Z]{2,}[A-Za-z0-9/_-]*|[A-Z][a-z][A-Za-z0-9/_-]*)"
        r"(?:\s+(?:[A-Z]{2,}[A-Za-z0-9/_-]*|[A-Z][a-z][A-Za-z0-9/_-]*))*\b"
    )
    mentions: list[dict] = []
    seen: set[str] = set()
    for match in pattern.finditer(segment_text):
        text = match.group(0).strip()
        text = re.sub(r"^(?:The|A|An)\s+", "", text)
        key = text.casefold()
        if len(text) < 2 or key in seen:
            continue
        seen.add(key)
        mentions.append(
            {
                "mention_id": f"m{len(mentions) + 1}",
                "text": text,
                "mention_type": "entity",
                "confidence": 0.72,
                "_start": match.start(),
                "_end": match.end(),
            }
        )
    if not mentions:
        mentions.append(
            {
                "mention_id": "m1",
                "text": "system",
                "mention_type": "entity",
                "confidence": 0.5,
                "_start": 0,
                "_end": 0,
            }
        )
    return mentions


def _heuristic_relations(segment_text: str, mentions: list[dict]) -> list[dict]:
    relation_patterns = (
        (r"\bdepends\s+on\b", "depends_on"),
        (r"\bretries?\b", "retries"),
        (r"\buses?\b", "uses"),
        (r"\brequires?\b", "depends_on"),
        (r"\baffects?\b", "affects"),
        (r"\bincreases?\b", "increases"),
        (r"\bdecreases?\b", "decreases"),
        (r"\bpart\s+of\b", "part_of"),
        (r"\bincludes?\b", "includes"),
        (r"\bachieves?\b", "achieves"),
    )
    relations: list[dict] = []
    positioned = [
        item for item in mentions
        if isinstance(item.get("_start"), int)
    ]
    for expression, predicate in relation_patterns:
        for match in re.finditer(expression, segment_text, flags=re.IGNORECASE):
            before = [item for item in positioned if item.get("_end", 0) <= match.start()]
            after = [item for item in positioned if item.get("_start", 0) >= match.end()]
            if not before or not after:
                continue
            subject = max(before, key=lambda item: int(item.get("_end", 0)))
            obj = min(after, key=lambda item: int(item.get("_start", 0)))
            if subject["mention_id"] == obj["mention_id"]:
                continue
            relations.append(
                {
                    "subject_mention_id": subject["mention_id"],
                    "predicate": predicate,
                    "object_mention_id": obj["mention_id"],
                    "evidence": segment_text,
                    "confidence": 0.68,
                }
            )

    measurement_mentions = [
        item for item in mentions if item.get("mention_type") == "measurement"
    ]
    non_measurements = [
        item for item in mentions if item.get("mention_type") != "measurement"
    ]
    for measurement in measurement_mentions:
        if not non_measurements:
            continue
        subject = min(
            non_measurements,
            key=lambda item: abs(
                int(item.get("_start", 0)) - int(measurement.get("_start", 0))
            ),
        )
        relations.append(
            {
                "subject_mention_id": subject["mention_id"],
                "predicate": "has_measurement",
                "object_mention_id": measurement["mention_id"],
                "evidence": segment_text,
                "confidence": 0.64,
            }
        )

    if not relations and len(mentions) >= 2:
        relations.append(
            {
                "subject_mention_id": mentions[0]["mention_id"],
                "predicate": "related_to",
                "object_mention_id": mentions[1]["mention_id"],
                "evidence": segment_text,
                "confidence": 0.5,
            }
        )
    return relations


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


def _parse_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Joint graph extractor response must be a JSON object")
    return parsed


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
