from pathlib import Path
from types import SimpleNamespace

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


def test_visualize_bundle_cli_passes_paths_and_reports_outputs(
    monkeypatch,
) -> None:
    captured = {}

    def fake_build_dashboard_bundle(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            index_path=Path("export/index.html"),
            global_path=Path("export/evolex-global-kg.html"),
            document_paths={"DOC-a": Path("export/documents/a.html")},
        )

    monkeypatch.setattr(
        "evolex.cli.build_dashboard_bundle",
        fake_build_dashboard_bundle,
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "visualize-bundle",
            "--output-dir",
            "export",
            "--canonical-dir",
            "canonical",
            "--registry-dir",
            "registry",
            "--schema-dir",
            "schema",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "output_dir": Path("export"),
        "canonical_dir": Path("canonical"),
        "registry_dir": Path("registry"),
        "schema_dir": Path("schema"),
    }
    assert "index: export/index.html" in result.output
    assert "global: export/evolex-global-kg.html" in result.output
    assert "document pages: 1" in result.output
