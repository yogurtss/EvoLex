from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from evolex.agents.deepseek_client import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

ChatAction = Literal[
    "exit",
    "process_text",
    "process_file",
    "show_last_result",
    "show_candidate_path",
    "show_entities",
    "show_relations",
    "show_quality",
    "set_pipeline_phase1",
    "set_pipeline_phase2",
    "help",
]
IntentLogCallback = Callable[[str, str], None]
IntentSource = Literal["command", "path", "llm", "rules", "fallback"]


@dataclass(frozen=True)
class ChatIntent:
    action: ChatAction
    payload: str = ""
    source: IntentSource = "rules"


EXIT_COMMANDS = {"exit", "quit", "q", "bye"}
HELP_COMMANDS = {"help", "?"}
LAST_RESULT_COMMANDS = {"last", "result", "show last"}
PATH_COMMANDS = {"path", "candidate path", "show path"}
ENTITIES_COMMANDS = {"entities", "show entities", "list entities"}
RELATIONS_COMMANDS = {"relations", "show relations", "list relations"}
QUALITY_COMMANDS = {"quality", "show quality", "quality scores"}
PIPELINE_PHASE1_COMMANDS = {"phase1", "phase 1", "p1", "use phase1"}
PIPELINE_PHASE2_COMMANDS = {"phase2", "phase 2", "p2", "full", "use phase2"}
COMMANDS = tuple(
    sorted(
        EXIT_COMMANDS
        | HELP_COMMANDS
        | LAST_RESULT_COMMANDS
        | PATH_COMMANDS
        | ENTITIES_COMMANDS
        | RELATIONS_COMMANDS
        | QUALITY_COMMANDS
        | PIPELINE_PHASE1_COMMANDS
        | PIPELINE_PHASE2_COMMANDS
    )
)

DOMAIN_HINTS = (
    "api",
    "database",
    "service",
    "pipeline",
    "latency",
    "throughput",
    "retry",
    "timeout",
    "schema",
    "version",
    "deployment",
    "model",
    "temperature",
    "voltage",
    "resistance",
)


def classify_intent(
    user_input: str,
    cwd: Path | None = None,
    on_event: IntentLogCallback | None = None,
    use_llm: bool = True,
) -> ChatIntent:
    text = user_input.strip()
    normalized = text.lower()

    if not text:
        return ChatIntent("help")

    if normalized in EXIT_COMMANDS:
        return ChatIntent("exit", source="command")

    if normalized in HELP_COMMANDS:
        return ChatIntent("help", source="command")

    if normalized in LAST_RESULT_COMMANDS:
        return ChatIntent("show_last_result", source="command")

    if normalized in PATH_COMMANDS:
        return ChatIntent("show_candidate_path", source="command")

    if normalized in ENTITIES_COMMANDS:
        return ChatIntent("show_entities", source="command")

    if normalized in RELATIONS_COMMANDS:
        return ChatIntent("show_relations", source="command")

    if normalized in QUALITY_COMMANDS:
        return ChatIntent("show_quality", source="command")

    if normalized in PIPELINE_PHASE1_COMMANDS:
        return ChatIntent("set_pipeline_phase1", source="command")

    if normalized in PIPELINE_PHASE2_COMMANDS:
        return ChatIntent("set_pipeline_phase2", source="command")

    explicit_file = _strip_file_prefix(text)
    for candidate_path in _candidate_file_paths(explicit_file, cwd=cwd):
        if candidate_path.exists() and candidate_path.is_file():
            return ChatIntent("process_file", str(candidate_path), source="path")

    if _looks_like_file_path(explicit_file) and not _looks_like_natural_language_command(text):
        return ChatIntent("process_file", str(_candidate_file_paths(explicit_file, cwd=cwd)[0]), source="path")

    if use_llm:
        llm_intent = _classify_intent_with_llm(text, cwd=cwd, on_event=on_event)
        if llm_intent is not None:
            return llm_intent

    natural_language_intent = _classify_natural_language_intent(text, cwd=cwd)
    if natural_language_intent is not None:
        return natural_language_intent

    if _looks_like_document_text(text):
        return ChatIntent("process_text", text, source="fallback")

    return ChatIntent("help", source="fallback")


def _looks_like_natural_language_command(text: str) -> bool:
    lowered = text.strip().lower()
    prefixes = (
        "我想",
        "帮我",
        "请",
        "查看",
        "看一下",
        "看下",
        "显示",
        "列出",
        "解析",
        "处理",
        "抽取",
        "运行",
        "show",
        "list",
        "view",
        "see",
        "check",
        "process",
        "parse",
        "extract",
        "run",
        "i want",
        "please",
        "can you",
    )
    return lowered.startswith(prefixes)


def _strip_file_prefix(text: str) -> str:
    text = text.strip().strip("\"'")
    for prefix in ("file:", "path:"):
        if text.lower().startswith(prefix):
            return text[len(prefix) :].strip().strip("\"'")
    return text


def _classify_natural_language_intent(text: str, cwd: Path | None = None) -> ChatIntent | None:
    view_target = _strip_leading_phrase(
        text,
        (
            "我想查看",
            "我想看",
            "帮我查看",
            "帮我看",
            "请查看",
            "请看",
            "查看",
            "看一下",
            "看下",
            "显示",
            "列出",
            "show me",
            "i want to view",
            "i want to see",
            "i want to check",
            "please view",
            "please show",
            "please list",
            "can you show",
            "can you list",
            "show",
            "list",
            "view",
            "see",
            "check",
        ),
    )
    if view_target is not None:
        return _classify_view_target(view_target)

    process_payload = _strip_leading_phrase(
        text,
        (
            "我想解析",
            "我想处理",
            "帮我解析",
            "帮我处理",
            "请解析",
            "请处理",
            "解析一下",
            "处理一下",
            "解析下",
            "处理下",
            "解析",
            "处理",
            "抽取",
            "运行",
            "process",
            "i want to parse",
            "i want to process",
            "i want to extract",
            "please parse",
            "please process",
            "please extract",
            "can you parse",
            "can you process",
            "can you extract",
            "parse",
            "extract",
            "run",
        ),
    )
    if process_payload is not None:
        return _classify_process_payload(process_payload, cwd=cwd)

    return None


def _strip_leading_phrase(text: str, phrases: tuple[str, ...]) -> str | None:
    stripped = text.strip()
    lowered = stripped.lower()
    for phrase in phrases:
        if lowered.startswith(phrase):
            return stripped[len(phrase) :].strip(" ：:，,")
    return None


def _classify_view_target(target: str) -> ChatIntent:
    normalized = target.strip().lower()
    compact = normalized.replace(" ", "")

    if not normalized:
        return ChatIntent("show_last_result", source="rules")
    if any(keyword in compact for keyword in ("实体", "entity", "entities")):
        return ChatIntent("show_entities", source="rules")
    if any(keyword in compact for keyword in ("关系", "relation", "relations")):
        return ChatIntent("show_relations", source="rules")
    if any(keyword in compact for keyword in ("质量", "评分", "分数", "quality", "score")):
        return ChatIntent("show_quality", source="rules")
    if any(keyword in compact for keyword in ("路径", "输出", "文件", "candidate", "path", "output")):
        return ChatIntent("show_candidate_path", source="rules")
    if any(keyword in compact for keyword in ("结果", "上次", "最近", "last", "result")):
        return ChatIntent("show_last_result", source="rules")
    if any(keyword in compact for keyword in ("帮助", "命令", "help", "command")):
        return ChatIntent("help", source="rules")
    if any(keyword in compact for keyword in ("阶段一", "phase1", "p1")):
        return ChatIntent("set_pipeline_phase1", source="rules")
    if any(keyword in compact for keyword in ("阶段二", "phase2", "p2", "full")):
        return ChatIntent("set_pipeline_phase2", source="rules")

    return ChatIntent("show_last_result", source="rules")


def _classify_process_payload(payload: str, cwd: Path | None = None) -> ChatIntent:
    cleaned = _strip_process_fillers(payload)
    if not cleaned:
        return ChatIntent("help", source="rules")

    explicit_file = _strip_file_prefix(cleaned)
    for candidate_path in _candidate_file_paths(explicit_file, cwd=cwd):
        if candidate_path.exists() and candidate_path.is_file():
            return ChatIntent("process_file", str(candidate_path), source="rules")

    if _looks_like_file_path(explicit_file):
        return ChatIntent("process_file", str(_candidate_file_paths(explicit_file, cwd=cwd)[0]), source="rules")

    return ChatIntent("process_text", cleaned, source="rules")


def _classify_intent_with_llm(
    text: str,
    cwd: Path | None = None,
    on_event: IntentLogCallback | None = None,
) -> ChatIntent | None:
    if not _llm_intent_available():
        if on_event is not None:
            on_event("intent", "LLM intent parser unavailable; using local rules.")
        return None

    if on_event is not None:
        on_event("intent", "Asking LLM to classify the user request.")

    try:
        raw = _call_llm_intent_parser(text)
        if on_event is not None:
            on_event("intent", f"LLM intent JSON: {_compact_json(raw)}")
        return _intent_from_llm_payload(raw, original_text=text, cwd=cwd)
    except Exception as exc:
        if on_event is not None:
            on_event("intent", f"LLM intent parser failed; using local rules. error={exc}")
        return None


def _llm_intent_available() -> bool:
    return os.environ.get("EVOLEX_OFFLINE") != "1" and bool(os.environ.get("DEEPSEEK_API_KEY"))


def _call_llm_intent_parser(text: str) -> dict:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI SDK is required for LLM intent parsing.") from exc

    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=DEEPSEEK_BASE_URL,
        timeout=15,
    )
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an intent parser for a bilingual English/Chinese CLI. "
                    "Return only one JSON object, no Markdown. "
                    "Allowed actions: exit, help, show_last_result, show_candidate_path, "
                    "show_entities, show_relations, show_quality, set_pipeline_phase1, "
                    "set_pipeline_phase2, process_file, process_text. "
                    "Use process_file when the user asks to parse/process/extract a local path. "
                    "Use process_text when the user provides document text or asks to parse inline text. "
                    "Payload should be the file path or document text only; otherwise empty."
                ),
            },
            {"role": "user", "content": text},
        ],
        stream=False,
        reasoning_effort="low",
        extra_body={"thinking": {"type": "disabled"}},
    )
    content = response.choices[0].message.content or "{}"
    parsed = _parse_json_object(content)
    if not isinstance(parsed, dict):
        raise ValueError("LLM intent response must be a JSON object")
    return parsed


def _parse_json_object(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def _intent_from_llm_payload(
    payload: dict,
    original_text: str,
    cwd: Path | None = None,
) -> ChatIntent:
    action = str(payload.get("action", "")).strip()
    intent_payload = str(payload.get("payload", "")).strip()
    allowed_actions = set(ChatAction.__args__)  # type: ignore[attr-defined]
    if action not in allowed_actions:
        raise ValueError(f"unknown LLM action: {action}")

    if action in ("process_file", "process_text"):
        intent_payload = intent_payload or original_text
        if action == "process_file":
            return _normalize_process_file_payload(intent_payload, cwd=cwd, source="llm")
        return ChatIntent("process_text", intent_payload, source="llm")

    return ChatIntent(action, intent_payload, source="llm")  # type: ignore[arg-type]


def _normalize_process_file_payload(
    payload: str,
    cwd: Path | None,
    source: IntentSource,
) -> ChatIntent:
    explicit_file = _strip_file_prefix(payload)
    for candidate_path in _candidate_file_paths(explicit_file, cwd=cwd):
        if candidate_path.exists() and candidate_path.is_file():
            return ChatIntent("process_file", str(candidate_path), source=source)
    return ChatIntent("process_file", str(_candidate_file_paths(explicit_file, cwd=cwd)[0]), source=source)


def _compact_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _strip_process_fillers(text: str) -> str:
    cleaned = text.strip().strip("\"'")
    for filler in ("一下", "下", "这个文件", "这个文档", "这份文件", "这份文档", "文件", "文档", "text", "file"):
        if cleaned.lower().startswith(filler):
            cleaned = cleaned[len(filler) :].strip(" ：:，,").strip("\"'")
            break
    return cleaned


def _candidate_file_paths(text: str, cwd: Path | None = None) -> list[Path]:
    path = Path(text).expanduser()
    if path.is_absolute():
        return [path]

    candidates: list[Path] = []
    if cwd is not None:
        candidates.append(cwd / path)
    candidates.append(_project_root() / path)

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved not in seen:
            unique.append(resolved)
            seen.add(resolved)
    return unique


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _looks_like_file_path(text: str) -> bool:
    path = Path(text)
    return "/" in text or "\\" in text or bool(path.suffix)


def _looks_like_document_text(text: str) -> bool:
    lowered = text.lower()
    if len(text) >= 40:
        return True
    return any(hint in lowered for hint in DOMAIN_HINTS)
