from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
ModelLogCallback = Callable[[str, str], None]


class BaseExtractor(ABC):
    uses_llm = False
    supports_relation_extraction = False

    @abstractmethod
    def extract(self, segment_text: str) -> list[dict]:
        raise NotImplementedError

    def extract_relations(self, atoms: list[dict], entities: list[dict]) -> list[dict]:
        raise NotImplementedError


class HeuristicExtractor(BaseExtractor):
    """Stable no-network extractor for local smoke tests and missing API keys."""

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


class DeepSeekExtractor(BaseExtractor):
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


def get_default_extractor(on_event: ModelLogCallback | None = None) -> BaseExtractor:
    if os.environ.get("EVOLEX_OFFLINE") == "1":
        return HeuristicExtractor()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if api_key:
        return DeepSeekExtractor(api_key=api_key, on_event=on_event)
    return HeuristicExtractor()


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
