from pathlib import Path
from typing import Optional

import typer

from evolex import __version__
from evolex.agents.deepseek_client import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, LLMConfig
from evolex.chat.repl import run_repl
from evolex.config import load_config
from evolex.graph.runner import normalize_pipeline

app = typer.Typer(help="EvoLex technical document knowledge-system CLI.")


def _complete_pipeline(incomplete: str) -> list[str]:
    return [
        mode
        for mode in ("system", "full", "phase3", "phase2", "phase1")
        if mode.startswith(incomplete)
    ]


@app.command()
def chat(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Directory for Phase 1 candidate JSONL outputs.",
    ),
    pipeline: str = typer.Option(
        "system",
        "--pipeline",
        help="Pipeline mode. Default is the complete system; use phase2/phase1 only for debug compatibility.",
        autocompletion=_complete_pipeline,
    ),
    llm_base_url: Optional[str] = typer.Option(
        None,
        "--llm-base-url",
        help="OpenAI-compatible LLM base URL.",
    ),
    llm_model: Optional[str] = typer.Option(
        None,
        "--llm-model",
        help="LLM model name.",
    ),
    llm_api_key: Optional[str] = typer.Option(
        None,
        "--llm-api-key",
        envvar="DEEPSEEK_API_KEY",
        help="LLM API key. Defaults to DEEPSEEK_API_KEY when set.",
    ),
    llm_timeout: Optional[int] = typer.Option(
        None,
        "--llm-timeout",
        help="LLM request timeout in seconds.",
    ),
) -> None:
    """Start the EvoLex conversational agent CLI."""
    try:
        pipeline_mode = normalize_pipeline(pipeline)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    file_cfg = load_config()
    llm_config = LLMConfig(
        base_url=llm_base_url or file_cfg.get("base_url") or DEEPSEEK_BASE_URL,
        model=llm_model or file_cfg.get("model") or DEEPSEEK_MODEL,
        api_key=llm_api_key or file_cfg.get("api_key"),
        timeout_seconds=llm_timeout or file_cfg.get("timeout_seconds") or 30,
    )
    run_repl(output_dir=output_dir, pipeline=pipeline_mode, llm_config=llm_config)


@app.command()
def version() -> None:
    """Print the EvoLex package version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
