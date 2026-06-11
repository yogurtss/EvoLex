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


def test_pipeline_switch_commands() -> None:
    assert classify_intent("phase1").action == "set_pipeline_phase1"
    assert classify_intent("p1").action == "set_pipeline_phase1"
    assert classify_intent("use phase1").action == "set_pipeline_phase1"
    assert classify_intent("phase2").action == "set_pipeline_phase2"
    assert classify_intent("p2").action == "set_pipeline_phase2"
    assert classify_intent("full").action == "set_pipeline_phase2"
    assert classify_intent("use phase2").action == "set_pipeline_phase2"
    assert classify_intent("phase 2").action == "set_pipeline_phase2"


def test_llm_intent_parser_handles_english_view(monkeypatch) -> None:
    events: list[tuple[str, str]] = []

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("EVOLEX_OFFLINE", raising=False)
    monkeypatch.setattr(
        "evolex.chat.intents._call_llm_intent_parser",
        lambda _text: {"action": "show_relations", "payload": ""},
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
        lambda _text: {"action": "process_file", "payload": str(doc)},
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
