from pathlib import Path
from typing import Optional

import typer

from evolex import __version__
from evolex.chat.repl import run_repl
from evolex.graph.runner import normalize_pipeline

app = typer.Typer(help="EvoLex technical document knowledge-system CLI.")


def _complete_pipeline(incomplete: str) -> list[str]:
    return [
        mode
        for mode in ("phase1", "phase1+2", "phase2", "full")
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
        "phase1",
        "--pipeline",
        help="Pipeline mode: phase1, phase1+2, phase2, or full.",
        autocompletion=_complete_pipeline,
    ),
) -> None:
    """Start the EvoLex conversational agent CLI."""
    try:
        pipeline_mode = normalize_pipeline(pipeline)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    run_repl(output_dir=output_dir, pipeline=pipeline_mode)


@app.command()
def version() -> None:
    """Print the EvoLex package version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
