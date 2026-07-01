from __future__ import annotations

from pathlib import Path

from evolex.agentic.agents import AgentProposal, GraphCriticAgent, choose_highest_utility
from evolex.agentic.math import action_utility, binary_entropy, expected_information_gain
from evolex.agents.deepseek_client import HeuristicTypedExtractor
from evolex.graph.runner import Phase3RunResult, run_pipeline_text


def test_binary_entropy_and_information_gain() -> None:
    assert binary_entropy(0.0) == 0.0
    assert binary_entropy(1.0) == 0.0
    assert round(binary_entropy(0.5), 3) == 1.0
    assert expected_information_gain(0.8, 0.3) == 0.5
    assert expected_information_gain(0.3, 0.8) == 0.0


def test_action_utility_penalizes_cost_and_risk() -> None:
    cheap_safe = action_utility(0.5, cost=0.2, risk=0.1)
    costly_risky = action_utility(0.5, cost=2.0, risk=0.8)
    assert cheap_safe > costly_risky


def test_orchestrator_choice_uses_highest_utility() -> None:
    proposals = [
        AgentProposal.from_scores(
            agent_name="A",
            proposed_action="low",
            expected_information_gain_value=0.2,
            risk=0.0,
            cost=1.0,
            reason="low utility",
        ),
        AgentProposal.from_scores(
            agent_name="B",
            proposed_action="high",
            expected_information_gain_value=0.5,
            risk=0.0,
            cost=1.0,
            reason="high utility",
        ),
    ]

    selected = choose_highest_utility(proposals)

    assert selected is not None
    assert selected.proposed_action == "high"


def test_sparse_graph_triggers_relation_extract_proposal() -> None:
    state = {
        "entities": [
            {"entity_id": "ent-0001", "confidence": 0.8},
            {"entity_id": "ent-0002", "confidence": 0.8},
        ],
        "relations": [],
        "agent_trace": [{"selected_action": "entity_resolve_tool"}],
    }

    proposals = GraphCriticAgent().propose(
        state,
        {
            "state_uncertainty": 0.8,
            "relation_uncertainty": 1.0,
            "entity_uncertainty": 0.4,
            "claim_uncertainty": 0.4,
            "schema_uncertainty": 0.4,
            "evidence_uncertainty": 0.4,
        },
        {"entity_resolve_tool"},
    )

    assert any(item.proposed_action == "relation_extract_tool" for item in proposals)


def test_agentic_pipeline_records_trace_and_scores(tmp_path: Path) -> None:
    result = run_pipeline_text(
        "ICP etching at 20mTorr with SF6/O2 chemistry achieves 2.5µm/min etch rate.",
        pipeline="agent",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
    )

    assert isinstance(result, Phase3RunResult)
    assert result.state.get("agent_trace")
    assert result.state.get("uncertainty_scores")
    assert result.state.get("information_gain_scores") is not None
    assert result.state.get("graph_quality_metrics")
    assert result.state.get("publish_confidence") is not None
    assert result.claim_count >= 1
    assert result.evidence_count >= 1


def test_agentic_pipeline_downgrades_sparse_publish(tmp_path: Path) -> None:
    result = run_pipeline_text(
        "The API Gateway retries HTTP 503 responses.",
        pipeline="agent",
        output_dir=tmp_path,
        extractor=HeuristicTypedExtractor(),
    )

    if result.relation_count == 0:
        assert result.policy_action in ("candidate", "quarantine", "reject")
        assert result.publish_output_path == ""
