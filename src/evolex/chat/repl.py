from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from evolex.agents.deepseek_client import LLMConfig
from evolex.chat.controller import ChatController
from evolex.graph.runner import PipelineAlias

COMPLETION_COMMANDS = (
    "help",
    "last",
    "path",
    "entities",
    "relations",
    "quality",
    "candidates",
    "quarantine",
    "policy",
    "schema",
    "audit",
    "llm settings",
    "set llm url ",
    "set llm model ",
    "set llm api-key ",
    "set llm timeout ",
    "exit",
    "q",
)

SLASH_COMMANDS = (
    "/help",
    "/exit",
    "/q",
    "/last",
    "/path",
    "/entities",
    "/relations",
    "/quality",
    "/candidates",
    "/quarantine",
    "/policy",
    "/schema",
    "/audit",
    "/settings",
    "/config",
    "/system",
    "/agent",
    "/agentic",
    "/phase3",
    "/phase2",
    "/phase1",
)


def run_repl(
    output_dir: Path | None = None,
    pipeline: PipelineAlias = "phase3",
    llm_config: LLMConfig | None = None,
) -> None:
    controller = ChatController(
        output_dir=output_dir,
        pipeline=pipeline,
        llm_config=llm_config,
    )
    completer = _install_readline_completion(controller.cwd)

    try:
        if controller.use_rich:
            _print_welcome_rich(pipeline)
        else:
            print(f"Agent> EvoLex conversational CLI is ready. System pipeline: {pipeline}.")
            print("Agent> Paste technical document text, or enter a local file path. Type help for commands.")

        while True:
            try:
                user_input = input("EvoLex> ")
            except (EOFError, KeyboardInterrupt):
                print("\nAgent> Exited.")
                return

            if controller.use_rich and _needs_progress(user_input):
                response = _run_with_spinner(controller, user_input)
            else:
                event_lines: list[str] = []
                response = controller.handle(
                    user_input,
                    on_event=lambda stage, message: event_lines.append(_format_event(stage, message)),
                )
                if event_lines:
                    response.text = "\n".join(event_lines + [response.text])

            print(response.text)
            if response.should_exit:
                return
    finally:
        if completer is not None:
            completer.restore()


def _needs_progress(user_input: str) -> bool:
    """Use progress UI for document runs and non-command natural language."""
    from evolex.chat.intents import classify_intent

    stripped = user_input.strip()
    if not stripped:
        return False
    intent = classify_intent(stripped, use_llm=False)
    return intent.action in ("process_text", "process_file") or intent.source not in ("command", "path")


def _run_with_spinner(controller: ChatController, user_input: str):
    """Run controller.handle() with a rich live progress panel."""
    from rich.console import Console
    from rich.live import Live

    console = Console()
    intermediate_lines: list[str] = []
    progress = _ProgressState(stages=_pipeline_stages(controller.pipeline))

    from evolex.chat.intents import classify_intent

    with Live(_render_progress(progress), refresh_per_second=10, console=console) as live:
        try:
            intent = classify_intent(
                user_input,
                cwd=controller.cwd,
                llm_config=controller.llm_config,
                on_event=lambda stage, message: _update_progress(live, progress, _format_event(stage, message), intermediate_lines),
            )
            if intent.action not in ("process_text", "process_file"):
                response = controller.handle_intent(intent)
                if intermediate_lines:
                    response.text = "\n".join(intermediate_lines + [response.text])
                return response

            result = controller.process_intent(
                intent,
                on_node=lambda node: _complete_progress_node(live, progress, node, intermediate_lines),
                on_event=lambda stage, message: _update_progress(live, progress, _format_event(stage, message), intermediate_lines),
            )
            controller.last_result = result
            progress.output_path = result.candidate_output_path
            progress.status = result.status
            progress.current = "complete"
            live.update(_render_progress(progress))
            formatted = controller._format_result(result)
            final_text = "\n".join(intermediate_lines) + "\n" + formatted

        except RuntimeError as exc:
            progress.status = "failed"
            progress.error = str(exc)
            live.update(_render_progress(progress))
            final_text = (
                f"Agent> Run failed before candidate output was written.\n"
                f"       error: {exc}\n"
                f"       hint: use `set llm api-key ...`, pass --llm-api-key, export EVOLEX_API_KEY or DEEPSEEK_API_KEY, "
                f"or set EVOLEX_OFFLINE=1 for explicit local debug mode."
            )
        except OSError as exc:
            progress.status = "failed"
            progress.error = str(exc)
            live.update(_render_progress(progress))
            final_text = (
                f"Agent> Could not read the requested file.\n"
                f"       path: {intent.payload}\n"
                f"       error: {exc}"
            )

    from dataclasses import dataclass

    @dataclass
    class _Response:
        text: str
        should_exit: bool = False

    return _Response(text=final_text)


class _ReadlineCompleter:
    def __init__(self, previous_completer, previous_delims: str) -> None:
        self.previous_completer = previous_completer
        self.previous_delims = previous_delims

    def restore(self) -> None:
        try:
            import readline
        except ImportError:
            return
        readline.set_completer(self.previous_completer)
        readline.set_completer_delims(self.previous_delims)


def _install_readline_completion(cwd: Path) -> _ReadlineCompleter | None:
    try:
        import readline
    except ImportError:
        return None

    previous_completer = readline.get_completer()
    previous_delims = readline.get_completer_delims()

    def complete(text: str, state: int) -> str | None:
        candidates = _readline_completion_candidates(
            text=text,
            cwd=cwd,
            line_buffer=readline.get_line_buffer(),
            begidx=readline.get_begidx(),
        )
        try:
            return candidates[state]
        except IndexError:
            return None

    readline.set_completer(complete)
    readline.set_completer_delims(_path_friendly_delimiters(previous_delims))
    readline.parse_and_bind("tab: complete")
    return _ReadlineCompleter(previous_completer, previous_delims)


def _path_friendly_delimiters(delimiters: str) -> str:
    return "".join(char for char in delimiters if char not in "/\\:@")


def _readline_completion_candidates(
    text: str,
    cwd: Path,
    line_buffer: str,
    begidx: int,
) -> list[str]:
    token_prefix = _token_prefix_before_cursor(line_buffer, begidx)
    if text == "" and _looks_like_partial_path(token_prefix):
        candidates = _completion_candidates(token_prefix, cwd)
        return [
            candidate[len(token_prefix) :]
            for candidate in candidates
            if candidate.startswith(token_prefix)
        ]
    return _completion_candidates(text, cwd)


def _token_prefix_before_cursor(line_buffer: str, begidx: int) -> str:
    before_cursor = line_buffer[:begidx]
    token_start = max(before_cursor.rfind(" "), before_cursor.rfind("\t"), before_cursor.rfind("\n")) + 1
    return before_cursor[token_start:]


def _completion_candidates(text: str, cwd: Path) -> list[str]:
    if text.startswith("/"):
        command_candidates = [
            f"{cmd} "
            for cmd in SLASH_COMMANDS
            if cmd.startswith(text.lower())
        ]
        if command_candidates:
            return command_candidates

    prefix, path_text = _split_path_prefix(text)
    candidates: list[str] = []

    if not prefix and not path_text:
        return []

    if not _looks_like_partial_path(path_text):
        candidates.extend(
            f"{command} "
            for command in COMPLETION_COMMANDS
            if command.startswith(path_text.lower())
        )

    candidates.extend(prefix + candidate for candidate in _path_completion_candidates(path_text, cwd))
    return _dedupe(candidates)


def _split_path_prefix(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for prefix in ("file:", "path:"):
        if lowered.startswith(prefix):
            return text[: len(prefix)], text[len(prefix) :].lstrip()
    if text.startswith("@"):
        return "@", text[1:].lstrip()
    return "", text


def _looks_like_partial_path(text: str) -> bool:
    return any(sep in text for sep in ("/", "\\")) or text.startswith((".", "~"))


def _path_completion_candidates(text: str, cwd: Path) -> list[str]:
    raw = text or ""
    path = Path(raw).expanduser()
    is_dir_prefix = raw.endswith(("/", "\\"))
    if path.is_absolute():
        search_roots = [Path("/")]
        display_prefix = ""
    else:
        search_roots = [cwd, _project_root()]
        display_prefix = ""

    if is_dir_prefix:
        parent_path = path
        parent_text = raw.rstrip("/\\")
        name_prefix = ""
    else:
        parent_path = path.parent
        parent_text = str(path.parent)
        if parent_text == ".":
            parent_text = ""
        name_prefix = path.name
    completions: list[str] = []

    for root in search_roots:
        parent = parent_path if path.is_absolute() else root / parent_path
        try:
            children = sorted(parent.iterdir(), key=lambda child: (not child.is_dir(), child.name.lower()))
        except OSError:
            continue

        for child in children:
            if not child.name.startswith(name_prefix):
                continue
            if child.name.startswith(".") and not name_prefix.startswith("."):
                continue
            if path.is_absolute():
                candidate = str(child)
            else:
                candidate_path = Path(parent_text) / child.name if parent_text else Path(child.name)
                candidate = display_prefix + str(candidate_path)
            if child.is_dir():
                candidate += "/"
            else:
                candidate += " "
            completions.append(candidate)

    return completions


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


@dataclass
class _ProgressState:
    stages: list[str]
    started_at: float = field(default_factory=perf_counter)
    completed: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    current: str = "classifying"
    status: str = "running"
    output_path: str = ""
    error: str = ""


def _pipeline_stages(pipeline: str) -> list[str]:
    if pipeline in ("agent", "agentic"):
        return [
            "ingest",
            "profile",
            "segment",
            "extract",
            "validate",
            "candidate_store",
            "entity_resolve",
            "relation_extract",
            "quality_review",
            "schema_gap",
            "schema_proposer",
            "critic",
            "policy",
            "publish/registry_finalize",
        ]
    base = ["ingest", "profile", "segment", "extract", "validate", "candidate_store"]
    if pipeline == "phase1":
        return base
    if pipeline == "phase1+2":
        return base + ["entity_resolve", "relation_extract", "quality_review", "publish"]
    return base + [
        "entity_resolve",
        "relation_extract",
        "schema_gap",
        "schema_proposer",
        "quality_review",
        "critic",
        "policy",
        "quarantine/publish",
        "registry_finalize",
    ]


def _update_progress(live, progress: _ProgressState, line: str, lines: list[str]) -> None:
    lines.append(line)
    progress.events.append(line)
    progress.events = progress.events[-6:]
    live.update(_render_progress(progress))


def _complete_progress_node(live, progress: _ProgressState, node: str, lines: list[str]) -> None:
    line = _format_event("pipeline", f"Node completed: {node}")
    lines.append(line)
    progress.events.append(line)
    progress.events = progress.events[-6:]
    if node in ("quarantine", "publish"):
        if "quarantine/publish" not in progress.completed:
            progress.completed.append("quarantine/publish")
    if node not in progress.completed:
        progress.completed.append(node)
    progress.current = node
    live.update(_render_progress(progress))


def _render_progress(progress: _ProgressState):
    from rich.columns import Columns
    from rich.panel import Panel
    from rich.table import Table

    table = Table.grid(padding=(0, 1))
    table.add_column("state", width=9)
    table.add_column("node")
    for stage in progress.stages:
        if stage in progress.completed:
            state = "[green]done[/green]"
        elif progress.current == stage or (
            progress.current in ("quarantine", "publish") and stage == "quarantine/publish"
        ):
            state = "[cyan]active[/cyan]"
        else:
            state = "[dim]wait[/dim]"
        table.add_row(state, stage)

    event_table = Table.grid()
    elapsed = perf_counter() - progress.started_at
    event_table.add_row(f"[bold]status[/bold] {progress.status}")
    event_table.add_row(f"[bold]elapsed[/bold] {elapsed:.1f}s")
    if progress.output_path:
        event_table.add_row(f"[bold]output[/bold] {progress.output_path}")
    if progress.error:
        event_table.add_row(f"[red]error[/red] {progress.error[:120]}")
    if progress.events:
        event_table.add_row("")
        for event in progress.events[-5:]:
            event_table.add_row(event[:120])

    return Panel(
        Columns([table, event_table], equal=False, expand=True),
        title="EvoLex Pipeline Progress",
        border_style="cyan",
    )


def _update_live(live: Live, node_name: str, lines: list[str]) -> None:
    """Update the live display with the latest completed node."""
    lines.append(f"  {node_name}")
    from rich.panel import Panel

    panel = Panel(
        "\n".join(lines),
        title="Pipeline Progress",
        border_style="cyan",
    )
    live.update(panel)


def _format_event(stage: str, message: str) -> str:
    labels = {
        "intent": "[intent]",
        "pipeline": "[pipeline]",
        "llm": "[llm]",
    }
    return f"{labels.get(stage, f'[{stage}]')} {message}"


def _print_welcome_rich(pipeline: str) -> None:
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(
        Panel(
            "[bold]EvoLex[/bold] — Technical Document Knowledge System",
            subtitle=f"System pipeline: {pipeline}",
            style="bold green",
        )
    )
    console.print("[dim]Paste text or enter a file path. Type [bold]help[/bold] for commands, [bold]exit[/bold] to quit.[/dim]")
