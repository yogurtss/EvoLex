from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from evolex.chat.intents import ChatIntent, IntentLogCallback, classify_intent
from evolex.agents.deepseek_client import LLMConfig
from evolex.config import save_llm_config
from evolex.graph.runner import (
    Phase1RunResult,
    Phase2RunResult,
    Phase3RunResult,
    run_pipeline_file,
    run_pipeline_text,
)
from evolex.repositories.kg_store import KGStore


@dataclass
class ChatResponse:
    text: str
    should_exit: bool = False


class ChatController:
    def __init__(
        self,
        output_dir: Path | None = None,
        cwd: Path | None = None,
        pipeline: Literal["phase1", "phase1+2", "phase3"] = "phase3",
        llm_config: LLMConfig | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.cwd = cwd or Path.cwd()
        self.pipeline = pipeline
        self.llm_config = llm_config
        self.last_result: Phase1RunResult | Phase2RunResult | Phase3RunResult | None = None
        self.use_rich = _rich_available()

    def handle(
        self,
        user_input: str,
        on_event: IntentLogCallback | None = None,
    ) -> ChatResponse:
        intent = classify_intent(
            user_input,
            cwd=self.cwd,
            on_event=on_event,
            llm_config=self.llm_config,
        )
        return self.handle_intent(intent, on_event=on_event)

    def handle_intent(
        self,
        intent: ChatIntent,
        on_event: IntentLogCallback | None = None,
    ) -> ChatResponse:
        if intent.action == "exit":
            return ChatResponse("Agent> Exited.", should_exit=True)

        if intent.action == "help":
            return ChatResponse(self._help_text())

        if intent.action == "show_last_result":
            return ChatResponse(self._format_last_result())

        if intent.action == "show_candidate_path":
            return ChatResponse(self._format_candidate_path())

        if intent.action == "show_entities":
            return ChatResponse(self._format_entities())

        if intent.action == "show_relations":
            return ChatResponse(self._format_relations())

        if intent.action == "show_quality":
            return ChatResponse(self._format_quality())

        if intent.action == "show_llm_settings":
            return ChatResponse(self._format_llm_settings())

        if intent.action == "set_llm_base_url":
            return self._set_llm_base_url(intent.payload)

        if intent.action == "set_llm_model":
            return self._set_llm_model(intent.payload)

        if intent.action == "set_llm_api_key":
            return self._set_llm_api_key(intent.payload)

        if intent.action == "set_llm_timeout":
            return self._set_llm_timeout(intent.payload)

        if intent.action == "set_pipeline_system":
            return ChatResponse(
                f"Agent> Unified system mode is active. Current pipeline: {self.pipeline}."
            )

        if intent.action == "set_pipeline_phase1":
            return self._set_pipeline("phase1")

        if intent.action == "set_pipeline_phase2":
            return self._set_pipeline("phase1+2")

        if intent.action == "process_file":
            return self._process_file(intent, on_event=on_event)

        if intent.action == "process_text":
            return self._process_text(intent, on_event=on_event)

        return ChatResponse(self._help_text())

    # -- pipeline switching ---------------------------------------------------

    def _set_pipeline(self, mode: Literal["phase1", "phase1+2"]) -> ChatResponse:
        labels = {
            "phase1": "phase1 (extract-only debug path)",
            "phase1+2": "phase2 (legacy graph debug path)",
        }
        return ChatResponse(
            "Agent> EvoLex now runs as one complete system by default.\n"
            f"Agent> Requested {labels[mode]}, but chat stays on the unified system pipeline ({self.pipeline}).\n"
            "Agent> If you really want an internal stage for debugging, use `evolex chat --pipeline phase1` "
            "or call the stage-specific runner from Python."
        )

    # -- LLM settings ---------------------------------------------------------

    def _active_llm_config(self) -> LLMConfig:
        return self.llm_config or LLMConfig()

    def _set_llm_base_url(self, value: str) -> ChatResponse:
        base_url = value.strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            return ChatResponse("Agent> LLM base URL must start with http:// or https://.")
        self.llm_config = replace(self._active_llm_config(), base_url=base_url)
        save_llm_config(self.llm_config)
        return ChatResponse(f"Agent> LLM base URL updated: {base_url}")

    def _set_llm_model(self, value: str) -> ChatResponse:
        model = value.strip()
        if not model:
            return ChatResponse("Agent> LLM model cannot be empty.")
        self.llm_config = replace(self._active_llm_config(), model=model)
        save_llm_config(self.llm_config)
        return ChatResponse(f"Agent> LLM model updated: {model}")

    def _set_llm_api_key(self, value: str) -> ChatResponse:
        api_key = value.strip()
        self.llm_config = replace(self._active_llm_config(), api_key=api_key or None)
        save_llm_config(self.llm_config)
        if api_key:
            return ChatResponse("Agent> LLM API key updated: [configured]")
        return ChatResponse("Agent> LLM API key reset to the environment/default setting.")

    def _set_llm_timeout(self, value: str) -> ChatResponse:
        try:
            timeout = int(value.strip())
        except ValueError:
            return ChatResponse("Agent> LLM timeout must be a positive integer number of seconds.")
        if timeout <= 0:
            return ChatResponse("Agent> LLM timeout must be greater than zero.")
        self.llm_config = replace(self._active_llm_config(), timeout_seconds=timeout)
        save_llm_config(self.llm_config)
        return ChatResponse(f"Agent> LLM timeout updated: {timeout}s")

    def _format_llm_settings(self) -> str:
        config = self._active_llm_config()
        if config.api_key:
            api_key_status = "configured via CLI"
        elif config.resolved_api_key():
            api_key_status = "configured via DEEPSEEK_API_KEY"
        else:
            api_key_status = "not configured; runs require a key unless EVOLEX_OFFLINE=1"
        return "\n".join(
            [
                "Agent> LLM settings:",
                f"       base_url: {config.base_url}",
                f"       model: {config.model}",
                f"       api_key: {api_key_status}",
                f"       timeout: {config.timeout_seconds}s",
            ]
        )

    # -- processing -----------------------------------------------------------

    def process_intent(
        self,
        intent: ChatIntent,
        on_node: Callable[[str], None] | None = None,
        on_event: IntentLogCallback | None = None,
    ) -> Phase1RunResult | Phase2RunResult | Phase3RunResult:
        if intent.action == "process_text":
            return run_pipeline_text(
                intent.payload,
                pipeline=self.pipeline,
                output_dir=self.output_dir,
                on_node=on_node,
                on_event=on_event,
                llm_config=self.llm_config,
            )
        if intent.action == "process_file":
            return run_pipeline_file(
                Path(intent.payload),
                pipeline=self.pipeline,
                output_dir=self.output_dir,
                on_node=on_node,
                on_event=on_event,
                llm_config=self.llm_config,
            )
        msg = f"intent is not processable: {intent.action}"
        raise ValueError(msg)

    def _process_text(
        self,
        intent: ChatIntent,
        on_event: IntentLogCallback | None = None,
    ) -> ChatResponse:
        lines = ["Agent> I will process this as a short document and run the harness."]
        try:
            result = self.process_intent(
                intent,
                on_node=lambda node: lines.append(f"Agent> Node completed: {node}"),
                on_event=on_event,
            )
        except RuntimeError as exc:
            lines.append(_format_error(exc))
            return ChatResponse("\n".join(lines))
        self.last_result = result
        lines.append(self._format_result(result))
        return ChatResponse("\n".join(lines))

    def _process_file(
        self,
        intent: ChatIntent,
        on_event: IntentLogCallback | None = None,
    ) -> ChatResponse:
        path = Path(intent.payload)
        lines = [f"Agent> I will read {path} and run the harness."]
        try:
            result = self.process_intent(
                intent,
                on_node=lambda node: lines.append(f"Agent> Node completed: {node}"),
                on_event=on_event,
            )
        except OSError as exc:
            lines.append(_format_file_error(path, exc))
            return ChatResponse("\n".join(lines))
        except RuntimeError as exc:
            lines.append(_format_error(exc))
            return ChatResponse("\n".join(lines))
        self.last_result = result
        lines.append(self._format_result(result))
        return ChatResponse("\n".join(lines))

    # -- result display -------------------------------------------------------

    def _format_result(self, result: Phase1RunResult | Phase2RunResult | Phase3RunResult) -> str:
        if self.use_rich:
            return _format_rich_result(result)
        return _format_plain_result(result)

    def _format_last_result(self) -> str:
        if self.last_result is None:
            return "Agent> There is no run result yet. Paste document text or enter a file path."
        return self._format_result(self.last_result)

    def _format_candidate_path(self) -> str:
        if self.last_result is None:
            return "Agent> There is no candidate output path yet. Process a document first."
        return f"Agent> Candidate output: {self.last_result.candidate_output_path}"

    # -- Phase II display commands --------------------------------------------

    def _format_entities(self) -> str:
        if self.last_result is None:
            entities = self._load_latest_kg_records("entities")
            if not entities:
                return "Agent> No entities found. Run the system first, or publish a document to the KG."
            return _format_entity_list(entities, self.use_rich, source=self._latest_kg_path())
        entities = self.last_result.state.get("entities", [])
        if not entities:
            return "Agent> No entities found in the last run."
        return _format_entity_list(entities, self.use_rich)

    def _format_relations(self) -> str:
        if self.last_result is None:
            relations = self._load_latest_kg_records("relations")
            if not relations:
                return "Agent> No relations found. Run the system first, or publish a document to the KG."
            return _format_relation_list(relations, self.use_rich, source=self._latest_kg_path())
        relations = self.last_result.state.get("relations", [])
        if not relations:
            return "Agent> No relations found in the last run."
        return _format_relation_list(relations, self.use_rich)

    def _format_quality(self) -> str:
        if self.last_result is None:
            scores = self._load_latest_kg_records("quality")
            if not scores:
                return "Agent> No quality scores found. Run the system first, or publish a document to the KG."
            return _format_quality_list(scores, self.use_rich, source=self._latest_kg_path())
        scores = self.last_result.state.get("quality_scores", [])
        if not scores:
            return "Agent> No quality scores in the last run."
        return _format_quality_list(scores, self.use_rich)

    def _latest_kg_path(self) -> Path | None:
        kg_dir = self.output_dir or Path("data/kg")
        db_paths = sorted(
            kg_dir.glob("*.sqlite"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return db_paths[0] if db_paths else None

    def _load_latest_kg_records(self, record_type: Literal["entities", "relations", "quality"]) -> list[dict]:
        db_path = self._latest_kg_path()
        if db_path is None:
            return []
        store = KGStore(db_path)
        try:
            if record_type == "entities":
                return store.fetch_entities()
            if record_type == "relations":
                return store.fetch_relations()
            return store.fetch_quality_scores()
        finally:
            store.close()

    # -- help ----------------------------------------------------------------

    def _help_text(self) -> str:
        base = (
            "Agent> Paste technical document text, or enter a local file path.\n"
            "Agent> Commands: /help, /last, /path, /exit (or: help, last, path, exit).\n"
        )
        if self.pipeline in ("phase1+2", "phase3"):
            base += (
                "Agent> System commands: /entities, /relations, /quality, /settings.\n"
            )
        base += (
            "Agent> File references: file:path, path:path, @/path\n"
            "Agent> Config: /config show | model <name> | url <url> | key <key> | timeout <sec>\n"
            "Agent> EvoLex runs one complete system by default.\n"
            f"Agent> Current pipeline: {self.pipeline}."
        )
        return base


# -- plain-text formatting ---------------------------------------------------


def _format_plain_result(result: Phase1RunResult | Phase2RunResult | Phase3RunResult) -> str:
    lines = [
        "Agent> Completed:",
        f"       status: {result.status}",
        f"       segments: {result.segment_count}",
        f"       semantic_atoms: {result.semantic_atom_count}",
    ]
    if isinstance(result, (Phase2RunResult, Phase3RunResult)):
        lines.append(f"       entities: {result.entity_count}")
        lines.append(f"       relations: {result.relation_count}")
        lines.append(f"       publish: {result.publish_output_path}")
    if isinstance(result, Phase3RunResult):
        lines.append(f"       claims: {result.claim_count}")
        lines.append(f"       evidence: {result.evidence_count}")
        lines.append(f"       policy: {result.policy_action}")
    lines.append(f"       output: {result.candidate_output_path}")
    return "\n".join(lines)


def _format_entity_list(
    entities: list[dict],
    use_rich: bool,
    source: Path | None = None,
) -> str:
    if use_rich:
        title = "Entities" if source is None else f"Entities from {source}"
        return _format_rich_table(
            title=title,
            columns=["ID", "Canonical Text", "Type", "Merged", "Segments"],
            rows=[
                (
                    e.get("entity_id", ""),
                    e.get("canonical_text", ""),
                    e.get("type", ""),
                    str(e.get("merged_count", 1)),
                    ", ".join(e.get("segment_ids", [])),
                )
                for e in entities
            ],
        )
    lines = ["Agent> Entities:"]
    if source is not None:
        lines.append(f"       source: {source}")
    for e in entities:
        lines.append(
            f"       {e.get('entity_id')} | {e.get('canonical_text')} | "
            f"type={e.get('type')} | merged={e.get('merged_count')}"
        )
    return "\n".join(lines)


def _format_relation_list(
    relations: list[dict],
    use_rich: bool,
    source: Path | None = None,
) -> str:
    if use_rich:
        title = "Relations" if source is None else f"Relations from {source}"
        return _format_rich_table(
            title=title,
            columns=["ID", "Subject", "Predicate", "Object", "Confidence"],
            rows=[
                (
                    r.get("relation_id", ""),
                    r.get("subject_entity_id", ""),
                    r.get("predicate", ""),
                    r.get("object_entity_id", ""),
                    f"{r.get('confidence', 0):.2f}",
                )
                for r in relations
            ],
        )
    lines = ["Agent> Relations:"]
    if source is not None:
        lines.append(f"       source: {source}")
    for r in relations:
        lines.append(
            f"       {r.get('relation_id')} | {r.get('subject_entity_id')} "
            f"--[{r.get('predicate')}]--> {r.get('object_entity_id')} "
            f"(confidence={r.get('confidence', 0):.2f})"
        )
    return "\n".join(lines)


def _format_quality_list(
    scores: list[dict],
    use_rich: bool,
    source: Path | None = None,
) -> str:
    if use_rich:
        title = "Quality Scores" if source is None else f"Quality Scores from {source}"
        return _format_rich_table(
            title=title,
            columns=["Target", "Index", "Score", "Issues"],
            rows=[
                (
                    s.get("target_type", ""),
                    str(s.get("target_index", "")),
                    f"{s.get('score', 0):.2f}",
                    ", ".join(s.get("issues", [])),
                )
                for s in scores
            ],
        )
    lines = ["Agent> Quality Scores:"]
    if source is not None:
        lines.append(f"       source: {source}")
    for s in scores:
        issues = ", ".join(s.get("issues", [])) or "none"
        lines.append(
            f"       [{s.get('target_type')}#{s.get('target_index')}] "
            f"score={s.get('score', 0):.2f} issues={issues}"
        )
    return "\n".join(lines)


# -- rich formatting ---------------------------------------------------------


def _format_rich_result(result: Phase1RunResult | Phase2RunResult | Phase3RunResult) -> str:
    from rich.console import Console
    from rich.table import Table

    console = Console(force_terminal=True, width=100)
    table = Table(title=f"Run Result: {result.run_id}", style="bold cyan")
    table.add_column("Field", style="dim")
    table.add_column("Value")

    status_style = "green" if result.status in ("candidate", "published") else "red"
    table.add_row("Status", f"[{status_style}]{result.status}[/{status_style}]")
    table.add_row("Segments", str(result.segment_count))
    table.add_row("Semantic Atoms", str(result.semantic_atom_count))

    if isinstance(result, (Phase2RunResult, Phase3RunResult)):
        table.add_row("Entities", str(result.entity_count))
        table.add_row("Relations", str(result.relation_count))
        table.add_row("Publish Output", result.publish_output_path)
    if isinstance(result, Phase3RunResult):
        table.add_row("Claims", str(result.claim_count))
        table.add_row("Evidence", str(result.evidence_count))
        table.add_row("Policy", result.policy_action)

    table.add_row("Candidate Output", result.candidate_output_path)

    import io
    buf = io.StringIO()
    console.file = buf
    console.print(table)
    return buf.getvalue()


def _format_rich_table(title: str, columns: list[str], rows: list[tuple]) -> str:
    from rich.console import Console
    from rich.table import Table

    console = Console(force_terminal=True, width=120)
    table = Table(title=title, style="bold cyan")
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*row)

    import io
    buf = io.StringIO()
    console.file = buf
    console.print(table)
    return buf.getvalue()


# -- errors ------------------------------------------------------------------


def _format_error(exc: RuntimeError) -> str:
    return (
        "Agent> Run failed before candidate output was written.\n"
        f"       error: {exc}\n"
        "       hint: use `set llm api-key ...`, pass --llm-api-key, export DEEPSEEK_API_KEY, "
        "or set EVOLEX_OFFLINE=1 for explicit local debug mode."
    )


def _format_file_error(path: Path, exc: OSError) -> str:
    return (
        "Agent> Could not read the requested file.\n"
        f"       path: {path}\n"
        f"       error: {exc}"
    )


# -- helpers -----------------------------------------------------------------


def _rich_available() -> bool:
    try:
        import rich  # noqa: F401
    except ImportError:
        return False
    return True
