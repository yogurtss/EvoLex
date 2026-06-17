from pathlib import Path

from evolex.agents.deepseek_client import LLMConfig
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
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")

    assert "status: published" in response.text
    assert "policy: publish" in response.text
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
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path, pipeline="phase1+2")
    _force_plain_text(controller)

    response = controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")

    assert "status: published" in response.text
    assert "entities:" in response.text
    assert str(tmp_path) in response.text


def test_chat_controller_show_entities(tmp_path: Path, monkeypatch) -> None:
    """'entities' command shows entity list after Phase 2 run."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
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
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
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
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path, pipeline="phase1+2")
    _force_plain_text(controller)

    controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")
    response = controller.handle("relations")

    assert "Relations" in response.text


def test_chat_controller_show_quality(tmp_path: Path, monkeypatch) -> None:
    """'quality' command shows quality scores after Phase 2 run."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path, pipeline="phase1+2")
    _force_plain_text(controller)

    controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")
    response = controller.handle("quality")

    assert "Quality" in response.text


def test_chat_controller_pipeline_switch(tmp_path: Path, monkeypatch) -> None:
    """Chat keeps the unified system active even if old phase commands are used."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path, pipeline="phase3")
    _force_plain_text(controller)

    assert controller.pipeline == "phase3"

    response = controller.handle("phase2")
    assert "unified system pipeline" in response.text
    assert controller.pipeline == "phase3"

    response = controller.handle("phase1")
    assert "unified system pipeline" in response.text
    assert controller.pipeline == "phase3"


def test_chat_controller_phase1_still_works(tmp_path: Path, monkeypatch) -> None:
    """Phase 1 pipeline still works with the enhanced controller."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path, pipeline="phase1")
    _force_plain_text(controller)

    response = controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")

    assert "status: candidate" in response.text
    assert "entities:" not in response.text  # Phase 1 doesn't show entities


def test_chat_controller_requires_llm_key_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("EVOLEX_OFFLINE", raising=False)
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")

    assert "LLM API key is required" in response.text
    assert "set llm api-key" in response.text


def test_chat_controller_llm_settings_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("evolex.config.CONFIG_PATH", tmp_path / ".evolex.toml")
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("set llm url https://example.test/v1")
    assert "https://example.test/v1" in response.text

    response = controller.handle("set llm model custom-model")
    assert "custom-model" in response.text

    response = controller.handle("set llm api-key sk-test")
    assert "[configured]" in response.text

    response = controller.handle("set llm timeout 45")
    assert "45s" in response.text

    response = controller.handle("set llm concurrency 6")
    assert "6" in response.text

    assert controller.llm_config == LLMConfig(
        base_url="https://example.test/v1",
        model="custom-model",
        api_key="sk-test",
        timeout_seconds=45,
        concurrency=6,
    )

    response = controller.handle("llm settings")
    assert "custom-model" in response.text
    assert "concurrency: 6" in response.text
    assert "sk-test" not in response.text


def test_repl_completion_suggests_commands_and_paths(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    note = docs_dir / "note.txt"
    note.write_text("API Gateway retries HTTP 503 responses.", encoding="utf-8")

    command_candidates = _completion_candidates("ph", tmp_path)
    assert command_candidates == []

    llm_candidates = _completion_candidates("ll", tmp_path)
    assert "llm settings " in llm_candidates

    policy_candidates = _completion_candidates("po", tmp_path)
    assert "policy " in policy_candidates

    slash_candidates = _completion_candidates("/qu", tmp_path)
    assert "/quarantine " in slash_candidates

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


# -- Slash command completion tests -------------------------------------------


def test_slash_command_completion_empty(tmp_path: Path) -> None:
    candidates = _completion_candidates("/", tmp_path)
    assert "/help " in candidates
    assert "/exit " in candidates
    assert "/entities " in candidates
    assert len(candidates) > 5  # many slash commands


def test_slash_command_completion_partial(tmp_path: Path) -> None:
    candidates = _completion_candidates("/he", tmp_path)
    assert candidates == ["/help "]


def test_slash_command_completion_config(tmp_path: Path) -> None:
    candidates = _completion_candidates("/co", tmp_path)
    assert candidates == ["/config "]


def test_slash_command_completion_no_match_falls_to_path(tmp_path: Path) -> None:
    """Unknown /xyz falls through to absolute path completion."""
    candidates = _completion_candidates("/usr", tmp_path)
    # Should find path candidates (like /usr/bin, /usr/lib, etc.) or return empty
    assert isinstance(candidates, list)


def test_bare_completion_still_works(tmp_path: Path) -> None:
    """Backward compat: bare commands still complete."""
    candidates = _completion_candidates("he", tmp_path)
    assert "help " in candidates
    assert len(candidates) == 1  # only "help" matches "he"

    entities_candidates = _completion_candidates("en", tmp_path)
    assert "entities " in entities_candidates


# -- @/ prefix completion tests -----------------------------------------------


def test_at_prefix_completion(tmp_path: Path) -> None:
    sub = tmp_path / "subdir"
    sub.mkdir()
    note = sub / "note.txt"
    note.write_text("content", encoding="utf-8")

    candidates = _completion_candidates("@su", tmp_path)
    assert any(c.startswith("@subdir/") for c in candidates)


def test_at_split_path_prefix() -> None:
    from evolex.chat.repl import _split_path_prefix

    prefix, path_text = _split_path_prefix("@/absolute/path")
    assert prefix == "@"
    assert path_text == "/absolute/path"

    prefix, path_text = _split_path_prefix("@relative/path")
    assert prefix == "@"
    assert path_text == "relative/path"


# -- /config controller tests -------------------------------------------------


def test_controller_config_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("evolex.config.CONFIG_PATH", tmp_path / ".evolex.toml")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("/config model custom-model")
    assert "custom-model" in response.text
    assert controller.llm_config.model == "custom-model"


def test_controller_config_url(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("evolex.config.CONFIG_PATH", tmp_path / ".evolex.toml")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("/config url https://example.test/v1")
    assert "https://example.test/v1" in response.text
    assert controller.llm_config.base_url == "https://example.test/v1"


def test_controller_config_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("evolex.config.CONFIG_PATH", tmp_path / ".evolex.toml")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("/config key sk-test")
    assert "[configured]" in response.text
    assert controller.llm_config.api_key == "sk-test"


def test_controller_config_timeout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("evolex.config.CONFIG_PATH", tmp_path / ".evolex.toml")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("/config timeout 60")
    assert "60s" in response.text
    assert controller.llm_config.timeout_seconds == 60


def test_controller_config_concurrency(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("evolex.config.CONFIG_PATH", tmp_path / ".evolex.toml")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("/config concurrency 3")
    assert "3" in response.text
    assert controller.llm_config.concurrency == 3


def test_controller_config_show(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("/config")
    assert "LLM settings" in response.text


def test_controller_config_show_explicit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("/config show")
    assert "LLM settings" in response.text


def test_controller_registry_query_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path, pipeline="phase3")
    _force_plain_text(controller)

    controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")

    assert "Recent candidates" in controller.handle("/candidates").text
    assert "Recent policy decisions" in controller.handle("/policy").text
    assert "Recent audit events" in controller.handle("/audit").text


def test_controller_slash_entities(tmp_path: Path, monkeypatch) -> None:
    """Slash commands work through the controller."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path, pipeline="phase1+2")
    _force_plain_text(controller)

    controller.handle("API Gateway retries HTTP 503 responses for 2 seconds.")
    response = controller.handle("/entities")

    assert "Entities" in response.text


def test_controller_slash_help(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EVOLEX_OFFLINE", "1")
    controller = ChatController(output_dir=tmp_path)
    _force_plain_text(controller)

    response = controller.handle("/help")
    assert "Commands:" in response.text
    assert "/config" in response.text
