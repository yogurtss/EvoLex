from pathlib import Path

from evolex.chat.controller import ChatController
from evolex.chat.repl import (
    _completion_candidates,
    _path_friendly_delimiters,
    _readline_completion_candidates,
)
from evolex.graph.runner import Phase1RunResult


def _force_plain_text(controller: ChatController) -> None:
    """Force plain-text output for tests, even if rich is installed."""
    controller.use_rich = False


def test_chat_controller_processes_short_document(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")

    assert "status: candidate" in response.text
    assert str(tmp_path) in response.text


def test_chat_controller_reports_runtime_errors(tmp_path: Path, monkeypatch) -> None:
    def fail_run(*args, **kwargs):
        raise RuntimeError("DeepSeek API network error: test failure")

    monkeypatch.setattr("evolex.chat.controller.run_pipeline_text", fail_run)
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")

    assert "Run failed before candidate output was written." in response.text
    assert "DeepSeek API network error: test failure" in response.text


def test_chat_controller_includes_llm_events_in_plain_response(tmp_path: Path, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        kwargs["on_event"]("llm", "Semantic extraction model output: []")
        kwargs["on_node"]("extract")
        return Phase1RunResult(
            run_id="RUN-test",
            document_id="DOC-test",
            status="candidate",
            segment_count=1,
            semantic_atom_count=0,
            candidate_output_path=str(tmp_path / "out.jsonl"),
            state={
                "run_id": "RUN-test",
                "document_id": "DOC-test",
                "status": "candidate",
                "candidate_output_path": str(tmp_path / "out.jsonl"),
            },
        )

    monkeypatch.setattr("evolex.chat.controller.run_pipeline_text", fake_run)
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)
    event_lines: list[str] = []

    response = controller.handle(
        "API Gateway retries HTTP 503 responses for 2 seconds.",
        on_event=lambda stage, message: event_lines.append(f"[{stage}] {message}"),
    )
    response.text = "\n".join(event_lines + [response.text])

    assert "[llm] Semantic extraction model output: []" in response.text
    assert "Agent> Node completed: extract" in response.text


def test_chat_controller_phase2_processes_document(tmp_path: Path, monkeypatch) -> None:
    """Phase 2 pipeline processes document and shows entity/relation counts."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    controller = ChatController(output_dir=tmp_path, pipeline="phase1+2")
    _force_plain_text(controller)

    response = controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")

    assert "status: published" in response.text
    assert "entities:" in response.text
    assert str(tmp_path) in response.text


def test_chat_controller_show_entities(tmp_path: Path, monkeypatch) -> None:
    """'entities' command shows entity list after Phase 2 run."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    controller = ChatController(output_dir=tmp_path, pipeline="phase1+2")
    _force_plain_text(controller)

    controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")
    response = controller.handle("entities")

    assert "Entities" in response.text


def test_chat_controller_show_entities_from_latest_kg_without_last_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    producer = ChatController(output_dir=tmp_path, pipeline="phase1+2")
    _force_plain_text(producer)
    producer.handle("API Gateway retries HTTP 503 responses for 2 seconds.")

    viewer = ChatController(output_dir=tmp_path, pipeline="phase1+2")
    _force_plain_text(viewer)
    response = viewer.handle("entities")

    assert "Entities" in response.text
    assert "source:" in response.text
    assert "API" in response.text


def test_chat_controller_show_relations(tmp_path: Path, monkeypatch) -> None:
    """'relations' command shows relation list after Phase 2 run."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    controller = ChatController(output_dir=tmp_path, pipeline="phase1+2")
    _force_plain_text(controller)

    controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")
    response = controller.handle("relations")

    assert "Relations" in response.text


def test_chat_controller_show_quality(tmp_path: Path, monkeypatch) -> None:
    """'quality' command shows quality scores after Phase 2 run."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    controller = ChatController(output_dir=tmp_path, pipeline="phase1+2")
    _force_plain_text(controller)

    controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")
    response = controller.handle("quality")

    assert "Quality" in response.text


def test_chat_controller_pipeline_switch(tmp_path: Path, monkeypatch) -> None:
    """Controller can switch pipeline modes."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    controller = ChatController(output_dir=tmp_path, pipeline="phase1")
    _force_plain_text(controller)

    assert controller.pipeline == "phase1"

    response = controller.handle("phase2")
    assert "Switched" in response.text
    assert controller.pipeline == "phase1+2"

    response = controller.handle("phase1")
    assert "Switched" in response.text
    assert controller.pipeline == "phase1"


def test_chat_controller_phase1_still_works(tmp_path: Path, monkeypatch) -> None:
    """Phase 1 pipeline still works with the enhanced controller."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    controller = ChatController(output_dir=tmp_path, pipeline="phase1")
    _force_plain_text(controller)

    response = controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")

    assert "status: candidate" in response.text
    assert "entities:" not in response.text  # Phase 1 doesn't show entities


def test_repl_completion_suggests_commands_and_paths(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    note = docs_dir / "note.txt"
    note.write_text("API Gateway retries HTTP 503 responses.", encoding="utf-8")

    command_candidates = _completion_candidates("ph", tmp_path)
    assert "phase1 " in command_candidates
    assert "phase2 " in command_candidates
    assert "phase 1 " not in command_candidates

    path_candidates = _completion_candidates("docs/n", tmp_path)
    assert "docs/note.txt " in path_candidates


def test_repl_completion_keeps_path_as_one_word() -> None:
    delimiters = " \t\n/:\\"

    updated = _path_friendly_delimiters(delimiters)

    assert "/" not in updated
    assert "\\" not in updated
    assert ":" not in updated
    assert " " in updated


def test_repl_completion_empty_prompt_is_quiet(tmp_path: Path) -> None:
    assert _completion_candidates("", tmp_path) == []


def test_repl_completion_directory_context_only_shows_children(tmp_path: Path) -> None:
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    note = examples_dir / "technical_note.txt"
    note.write_text("API Gateway retries HTTP 503 responses.", encoding="utf-8")

    candidates = _completion_candidates("examples/", tmp_path)

    assert candidates == ["examples/technical_note.txt "]


def test_readline_completion_after_trailing_slash_returns_suffix(tmp_path: Path) -> None:
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    note = examples_dir / "technical_note.txt"
    note.write_text("API Gateway retries HTTP 503 responses.", encoding="utf-8")

    candidates = _readline_completion_candidates(
        text="",
        cwd=tmp_path,
        line_buffer="examples/",
        begidx=len("examples/"),
    )

    assert candidates == ["technical_note.txt "]
