from pathlib import Path

from evolex.chat.intents import classify_intent


def test_exit_intent() -> None:
    assert classify_intent("exit").action == "exit"


def test_file_intent(tmp_path: Path) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text(
        "API Gateway retries HTTP 503 responses for 2 seconds before failing over.",
        encoding="utf-8",
    )

    intent = classify_intent(str(doc))

    assert intent.action == "process_file"
    assert intent.payload == str(doc)


def test_text_intent() -> None:
    intent = classify_intent("API Gateway retries HTTP 503 responses for 2 seconds.")

    assert intent.action == "process_text"


def test_project_relative_example_path_from_other_cwd(tmp_path: Path) -> None:
    intent = classify_intent("examples/technical_note.txt", cwd=tmp_path)

    assert intent.action == "process_file"
    assert intent.payload.endswith("examples/technical_note.txt")


# -- Phase II intents --------------------------------------------------------


def test_entities_command() -> None:
    assert classify_intent("entities").action == "show_entities"
    assert classify_intent("show entities").action == "show_entities"
    assert classify_intent("list entities").action == "show_entities"


def test_relations_command() -> None:
    assert classify_intent("relations").action == "show_relations"
    assert classify_intent("show relations").action == "show_relations"
    assert classify_intent("list relations").action == "show_relations"


def test_quality_command() -> None:
    assert classify_intent("quality").action == "show_quality"
    assert classify_intent("show quality").action == "show_quality"
    assert classify_intent("quality scores").action == "show_quality"


def test_llm_settings_commands() -> None:
    assert classify_intent("llm settings").action == "show_llm_settings"
    assert classify_intent("model settings").action == "show_llm_settings"

    url_intent = classify_intent("set llm url https://example.test/v1")
    assert url_intent.action == "set_llm_base_url"
    assert url_intent.payload == "https://example.test/v1"

    model_intent = classify_intent("set llm model custom-model")
    assert model_intent.action == "set_llm_model"
    assert model_intent.payload == "custom-model"

    key_intent = classify_intent("set llm api-key sk-test")
    assert key_intent.action == "set_llm_api_key"
    assert key_intent.payload == "sk-test"

    timeout_intent = classify_intent("set llm timeout 45")
    assert timeout_intent.action == "set_llm_timeout"
    assert timeout_intent.payload == "45"


def test_pipeline_switch_commands() -> None:
    assert classify_intent("system").action == "set_pipeline_system"
    assert classify_intent("phase3").action == "set_pipeline_system"
    assert classify_intent("p3").action == "set_pipeline_system"
    assert classify_intent("full").action == "set_pipeline_system"
    assert classify_intent("phase1").action == "set_pipeline_phase1"
    assert classify_intent("p1").action == "set_pipeline_phase1"
    assert classify_intent("use phase1").action == "set_pipeline_phase1"
    assert classify_intent("phase2").action == "set_pipeline_phase2"
    assert classify_intent("p2").action == "set_pipeline_phase2"
    assert classify_intent("use phase2").action == "set_pipeline_phase2"
    assert classify_intent("phase 2").action == "set_pipeline_phase2"


def test_llm_intent_parser_handles_english_view(monkeypatch) -> None:
    events: list[tuple[str, str]] = []

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("EVOLEX_OFFLINE", raising=False)
    monkeypatch.setattr(
        "evolex.chat.intents._call_llm_intent_parser",
        lambda _text, llm_config=None: {"action": "show_relations", "payload": ""},
    )

    intent = classify_intent(
        "I want to view the relations from the last run",
        on_event=lambda stage, message: events.append((stage, message)),
    )

    assert intent.action == "show_relations"
    assert intent.source == "llm"
    assert events[0] == ("intent", "Asking LLM to classify the user request.")
    assert "show_relations" in events[1][1]


def test_llm_intent_parser_handles_chinese_process_file(tmp_path: Path, monkeypatch) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text("API Gateway retries HTTP 503 responses.", encoding="utf-8")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("EVOLEX_OFFLINE", raising=False)
    monkeypatch.setattr(
        "evolex.chat.intents._call_llm_intent_parser",
        lambda _text, llm_config=None: {"action": "process_file", "payload": str(doc)},
    )

    intent = classify_intent("我想解析这个文件", cwd=tmp_path)

    assert intent.action == "process_file"
    assert intent.source == "llm"
    assert intent.payload == str(doc)


def test_natural_language_rules_fallback_without_llm(monkeypatch) -> None:
    events: list[tuple[str, str]] = []

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    intent = classify_intent(
        "我想查看实体",
        on_event=lambda stage, message: events.append((stage, message)),
    )

    assert intent.action == "show_entities"
    assert intent.source == "rules"
    assert events == [("intent", "LLM intent parser unavailable; using local rules.")]


def test_english_process_falls_back_to_rules(tmp_path: Path, monkeypatch) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text("API Gateway retries HTTP 503 responses.", encoding="utf-8")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    intent = classify_intent(f"please process {doc}")

    assert intent.action == "process_file"
    assert intent.source == "rules"
    assert intent.payload == str(doc)


# -- Slash commands -----------------------------------------------------------


def test_slash_exit() -> None:
    assert classify_intent("/exit").action == "exit"


def test_slash_help() -> None:
    assert classify_intent("/help").action == "help"


def test_slash_entities() -> None:
    assert classify_intent("/entities").action == "show_entities"


def test_slash_relations() -> None:
    assert classify_intent("/relations").action == "show_relations"


def test_slash_quality() -> None:
    assert classify_intent("/quality").action == "show_quality"


def test_slash_last() -> None:
    assert classify_intent("/last").action == "show_last_result"


def test_slash_path() -> None:
    assert classify_intent("/path").action == "show_candidate_path"


def test_slash_settings() -> None:
    assert classify_intent("/settings").action == "show_llm_settings"
    assert classify_intent("/llm").action == "show_llm_settings"


def test_slash_pipeline() -> None:
    assert classify_intent("/system").action == "set_pipeline_system"
    assert classify_intent("/phase3").action == "set_pipeline_system"
    assert classify_intent("/phase2").action == "set_pipeline_phase2"
    assert classify_intent("/phase1").action == "set_pipeline_phase1"


def test_slash_unknown_falls_through() -> None:
    """Unknown /-prefixed text is treated as help, not a file path."""
    intent = classify_intent("/unknowncommand")
    assert intent.action == "help"


def test_slash_alone_shows_help() -> None:
    assert classify_intent("/").action == "help"


def test_bare_commands_still_work() -> None:
    """Backward compatibility: bare commands still work."""
    assert classify_intent("exit").action == "exit"
    assert classify_intent("help").action == "help"
    assert classify_intent("entities").action == "show_entities"
    assert classify_intent("relations").action == "show_relations"
    assert classify_intent("quality").action == "show_quality"
    assert classify_intent("last").action == "show_last_result"
    assert classify_intent("path").action == "show_candidate_path"


# -- /config subcommands ------------------------------------------------------


def test_config_show() -> None:
    assert classify_intent("/config").action == "show_llm_settings"
    assert classify_intent("/config show").action == "show_llm_settings"
    assert classify_intent("/config  show").action == "show_llm_settings"


def test_config_model() -> None:
    intent = classify_intent("/config model custom-model")
    assert intent.action == "set_llm_model"
    assert intent.payload == "custom-model"


def test_config_url() -> None:
    intent = classify_intent("/config url https://example.test/v1")
    assert intent.action == "set_llm_base_url"
    assert intent.payload == "https://example.test/v1"


def test_config_key() -> None:
    intent = classify_intent("/config key sk-test")
    assert intent.action == "set_llm_api_key"
    assert intent.payload == "sk-test"


def test_config_key_clears_without_value() -> None:
    intent = classify_intent("/config key")
    assert intent.action == "set_llm_api_key"
    assert intent.payload == ""


def test_config_timeout() -> None:
    intent = classify_intent("/config timeout 45")
    assert intent.action == "set_llm_timeout"
    assert intent.payload == "45"


def test_config_model_without_value_shows_settings() -> None:
    assert classify_intent("/config model").action == "show_llm_settings"


def test_config_timeout_without_value_shows_settings() -> None:
    assert classify_intent("/config timeout").action == "show_llm_settings"


def test_config_url_without_value_shows_settings() -> None:
    assert classify_intent("/config url").action == "show_llm_settings"


def test_config_unknown_subcommand_shows_settings() -> None:
    assert classify_intent("/config unknown").action == "show_llm_settings"


# -- @/ file references -------------------------------------------------------


def test_at_file_prefix_intent(tmp_path: Path) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text("API Gateway retries HTTP 503 responses.", encoding="utf-8")

    intent = classify_intent(f"@{doc}")

    assert intent.action == "process_file"
    assert intent.payload == str(doc)


def test_at_absolute_path_prefix(tmp_path: Path) -> None:
    doc = tmp_path / "test.txt"
    doc.write_text("Test content.", encoding="utf-8")

    intent = classify_intent(f"@{doc}")

    assert intent.action == "process_file"
    assert intent.payload == str(doc)


def test_at_prefix_without_path() -> None:
    intent = classify_intent("@")
    assert intent.action in ("help", "process_text")


def test_at_prefix_does_not_interfere_with_file_prefix(tmp_path: Path) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text("Content", encoding="utf-8")

    file_intent = classify_intent(f"file:{doc}")
    assert file_intent.action == "process_file"
    assert file_intent.payload == str(doc)

    path_intent = classify_intent(f"path:{doc}")
    assert path_intent.action == "process_file"
    assert path_intent.payload == str(doc)
