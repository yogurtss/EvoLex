from typer.testing import CliRunner

from evolex.agents.deepseek_client import LLMConfig
from evolex.cli import app


def test_chat_cli_passes_initial_llm_config(monkeypatch) -> None:
    captured = {}

    def fake_run_repl(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("evolex.cli.run_repl", fake_run_repl)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "chat",
            "--llm-base-url",
            "https://example.test/v1",
            "--llm-model",
            "custom-model",
            "--llm-api-key",
            "sk-test",
            "--llm-timeout",
            "45",
            "--llm-concurrency",
            "7",
        ],
    )

    assert result.exit_code == 0
    assert captured["llm_config"] == LLMConfig(
        base_url="https://example.test/v1",
        model="custom-model",
        api_key="sk-test",
        timeout_seconds=45,
        concurrency=7,
    )
