import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

import typer

from evolex import __version__
from evolex.agents.deepseek_client import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, LLMConfig
from evolex.chat.repl import run_repl
from evolex.config import load_config
from evolex.graph.runner import (
    normalize_pipeline,
    replay_run,
    resume_thread,
    run_frozen_evaluation,
    run_shadow_evaluation,
)
from evolex.repositories.schema_store import SchemaCandidateStore

app = typer.Typer(help="EvoLex technical document knowledge-system CLI.")
eval_app = typer.Typer(help="Run offline evaluation workflows.")
run_app = typer.Typer(help="Replay or resume checkpointed runs.")
schema_app = typer.Typer(help="Inspect and promote schema proposals.")
app.add_typer(eval_app, name="eval")
app.add_typer(run_app, name="run")
app.add_typer(schema_app, name="schema")


def _complete_pipeline(incomplete: str) -> list[str]:
    return [
        mode
        for mode in ("system", "agent", "agentic", "full", "phase3", "phase2", "phase1")
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
        help="Pipeline mode. Default is the complete system; use agent for information-gain multi-agent control.",
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
    llm_concurrency: Optional[int] = typer.Option(
        None,
        "--llm-concurrency",
        min=1,
        help="Maximum concurrent segment-level LLM extraction calls.",
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
        concurrency=llm_concurrency or file_cfg.get("concurrency") or 4,
        profile=file_cfg.get("profile"),
    )
    run_repl(output_dir=output_dir, pipeline=pipeline_mode, llm_config=llm_config)


@app.command()
def version() -> None:
    """Print the EvoLex package version."""
    typer.echo(__version__)


@eval_app.command("frozen")
def eval_frozen(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Directory for evaluation artifacts.",
    ),
    update_baseline: bool = typer.Option(
        False,
        "--update-baseline",
        help="Replace the frozen corpus baseline with this run.",
    ),
) -> None:
    """Run the frozen corpus regression baseline."""
    result = run_frozen_evaluation(
        output_dir=output_dir,
        update_baseline=update_baseline,
    )
    typer.echo("Frozen evaluation completed:")
    typer.echo(f"  documents: {result.document_count}")
    typer.echo(f"  report: {result.report_path}")
    typer.echo(f"  baseline: {result.baseline_path}")
    typer.echo(f"  claims: {result.report.get('totals', {}).get('claims', 0)}")
    typer.echo(f"  evidence: {result.report.get('totals', {}).get('evidence', 0)}")


@eval_app.command("shadow")
def eval_shadow(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Directory for evaluation artifacts.",
    ),
) -> None:
    """Run shadow evaluation without writing production KG."""
    result = run_shadow_evaluation(output_dir=output_dir)
    governance = result.report.get("governance", {})
    typer.echo("Shadow evaluation completed:")
    typer.echo(f"  documents: {result.document_count}")
    typer.echo(f"  report: {result.report_path}")
    typer.echo(f"  canary_ready: {governance.get('canary_ready')}")
    typer.echo(f"  rollback_recommended: {governance.get('rollback_recommended')}")


@run_app.command("replay")
def run_replay(
    run_id: str = typer.Option(..., "--run-id", help="Run ID to replay."),
    checkpoint_dir: Optional[Path] = typer.Option(
        None,
        "--checkpoint-dir",
        help="Directory containing checkpoint storage.",
    ),
) -> None:
    """Replay checkpointed node transitions for a run."""
    result = replay_run(run_id=run_id, checkpoint_dir=checkpoint_dir)
    if not result.events:
        typer.echo(f"No checkpoint events found for run: {run_id}")
        raise typer.Exit(code=1)
    typer.echo(f"Replay for {run_id}:")
    for event in result.events:
        typer.echo(
            f"  {event.get('step_index')}: {event.get('node_name')} "
            f"status={event.get('status')} decision={event.get('decision') or ''}"
        )


@run_app.command("resume")
def run_resume(
    thread_id: str = typer.Option(..., "--thread-id", help="Thread ID to resume."),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Directory for resumed run outputs.",
    ),
    checkpoint_dir: Optional[Path] = typer.Option(
        None,
        "--checkpoint-dir",
        help="Directory containing checkpoint storage.",
    ),
    pipeline: str = typer.Option(
        "system",
        "--pipeline",
        help="Pipeline mode to resume.",
    ),
) -> None:
    """Resume from the latest checkpoint for a thread."""
    try:
        normalize_pipeline(pipeline)
        result = resume_thread(
            thread_id=thread_id,
            output_dir=output_dir,
            checkpoint_dir=checkpoint_dir,
            pipeline=pipeline,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo("Run resumed:")
    typer.echo(f"  thread_id: {result.thread_id}")
    typer.echo(f"  from_node: {result.resumed_from_node}")
    typer.echo(f"  run_id: {result.result.run_id}")
    typer.echo(f"  status: {result.result.status}")


@schema_app.command("candidates")
def schema_candidates(
    schema_dir: Optional[Path] = typer.Option(
        None,
        "--schema-dir",
        help="Directory containing schema candidate storage.",
    ),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    """List schema proposals."""
    proposals = SchemaCandidateStore(schema_dir).get_proposals(limit=limit)
    if not proposals:
        typer.echo("No schema proposals found.")
        return
    for proposal in proposals:
        typer.echo(
            f"{proposal['proposal_id']} | {proposal['status']} | "
            f"{proposal['proposal_type']} | {proposal['name']} | "
            f"occurrences={proposal['occurrence_count']} docs={proposal['independent_document_count']}"
        )


@schema_app.command("promote-ready")
def schema_promote_ready(
    schema_dir: Optional[Path] = typer.Option(
        None,
        "--schema-dir",
        help="Directory containing schema candidate storage.",
    ),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    """List proposals that meet automatic promotion signal thresholds."""
    proposals = SchemaCandidateStore(schema_dir).get_promotion_candidates(limit=limit)
    if not proposals:
        typer.echo("No promotion-ready schema proposals found.")
        return
    for proposal in proposals:
        typer.echo(
            f"{proposal['proposal_id']} | {proposal['proposal_type']} | {proposal['name']} | "
            f"occurrences={proposal['occurrence_count']} docs={proposal['independent_document_count']}"
        )


@schema_app.command("promote")
def schema_promote(
    proposal_id: str = typer.Option(..., "--proposal-id", help="Schema proposal ID to promote."),
    schema_dir: Optional[Path] = typer.Option(
        None,
        "--schema-dir",
        help="Directory containing schema candidate storage.",
    ),
    target_schema_version: Optional[str] = typer.Option(
        None,
        "--target-schema-version",
        help="Target schema version to record in the promotion ledger.",
    ),
    eval_report: Optional[Path] = typer.Option(
        None,
        "--eval-report",
        help="Optional frozen/shadow report JSON used for automatic gate checks.",
    ),
) -> None:
    """Promote a schema proposal only if automatic gates pass."""
    store = SchemaCandidateStore(schema_dir)
    report = _load_eval_report(eval_report)
    decision = store.evaluate_promotion(proposal_id, eval_report=report)
    reason = ", ".join(decision.get("reasons", []))
    if decision["action"] == "promote":
        proposal = store.get_proposal_by_id(proposal_id)
        assert proposal is not None
        target = target_schema_version or _default_target_schema_version(proposal)
        store.promote_proposal(
            proposal_id,
            target_schema_version=target,
            reason=reason,
            report_path=str(eval_report) if eval_report else None,
        )
        typer.echo(f"Promoted {proposal_id} to {target}: {reason}")
        return
    if decision["action"] == "block":
        store.block_proposal(
            proposal_id,
            reason=reason,
            report_path=str(eval_report) if eval_report else None,
        )
        typer.echo(f"Blocked {proposal_id}: {reason}")
        return
    typer.echo(f"Held {proposal_id}: {reason}")
    raise typer.Exit(code=1)


@schema_app.command("promotions")
def schema_promotions(
    schema_dir: Optional[Path] = typer.Option(
        None,
        "--schema-dir",
        help="Directory containing schema candidate storage.",
    ),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    """List schema promotion/block ledger records."""
    records = SchemaCandidateStore(schema_dir).get_promotions(limit=limit)
    if not records:
        typer.echo("No schema promotion records found.")
        return
    for record in records:
        typer.echo(
            f"{record['proposal_id']} | {record['action']} | {record['name']} | "
            f"target={record['target_schema_version']} | reason={record['reason']}"
        )


def _load_eval_report(path: Path | None) -> dict | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _default_target_schema_version(proposal: dict) -> str:
    base = proposal.get("schema_version") or "schema"
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"{base}+{suffix}"


if __name__ == "__main__":
    app()
