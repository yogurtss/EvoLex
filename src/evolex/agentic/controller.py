from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from evolex.agentic.agents import (
    AgentProposal,
    choose_highest_utility,
    default_agents,
)
from evolex.agentic.math import summarize_uncertainty
from evolex.agentic.metrics import graph_metrics, publish_confidence
from evolex.agentic.tools import AgentTool, build_agent_tools, run_tool_with_audit
from evolex.agents.deepseek_client import BaseExtractor, LLMConfig, get_default_extractor
from evolex.graph.state import GraphState
from evolex.repositories.evaluation import CheckpointStore

NodeCallback = Callable[[str], None]
GraphLogCallback = Callable[[str, str], None]


DEFAULT_AGENT_BUDGET = {
    "max_rounds": 18,
    "max_low_eig_rounds": 2,
    "min_utility": -0.02,
    "publish_confidence_threshold": 0.45,
}


class AgenticKGRunner:
    """Information-gain controlled multi-agent runner.

    Existing pipeline nodes are exposed as tools. The orchestrator observes the
    current GraphState, asks specialized agents for proposals, scores them with
    expected information gain, cost, and risk, then executes the best action.
    """

    def __init__(
        self,
        extractor: BaseExtractor | None = None,
        output_dir: Path | None = None,
        on_event: GraphLogCallback | None = None,
        llm_config: LLMConfig | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        self.extractor = extractor or get_default_extractor(
            on_event=on_event,
            typed=True,
            llm_config=llm_config,
        )
        self.output_dir = output_dir
        self.checkpoint_store = checkpoint_store
        self.tools = build_agent_tools(self.extractor, output_dir)
        self.agents = default_agents()
        self._step_index = 0
        self._low_eig_rounds = 0

    def invoke(
        self,
        initial_state: GraphState,
        on_node: NodeCallback | None = None,
    ) -> GraphState:
        state: GraphState = dict(initial_state)
        state.setdefault("agent_trace", [])
        state.setdefault("agent_budget", dict(DEFAULT_AGENT_BUDGET))
        state.setdefault("active_questions", [])

        while not self._should_stop(state):
            budget = _budget(state)
            if len(state.get("agent_trace", [])) >= int(budget["max_rounds"]):
                self._budget_stop(state)
                break

            uncertainty = summarize_uncertainty(state)
            metrics = graph_metrics(state)
            pub_conf = publish_confidence(state)
            state["uncertainty_scores"] = uncertainty
            state["graph_quality_metrics"] = metrics
            state["publish_confidence"] = pub_conf
            state["active_questions"] = _active_questions(metrics)

            proposal = self._mandatory_proposal(state, uncertainty)
            proposals: list[AgentProposal]
            if proposal is not None:
                proposals = [proposal]
            else:
                proposals = self._collect_proposals(state, uncertainty)
                proposal = choose_highest_utility(proposals)

            state["information_gain_scores"] = [item.to_dict() for item in proposals]
            if proposal is None:
                self._no_action_stop(state)
                break

            if self._low_gain_stop(state, proposal):
                break

            self._record_trace(state, proposal, proposals, uncertainty, metrics, pub_conf)
            self._execute_tool(state, proposal, on_node=on_node)

        self._ensure_registry_finalized(state, on_node=on_node)
        return state

    def _mandatory_proposal(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
    ) -> AgentProposal | None:
        completed = _completed_tools(state)
        mandatory: list[tuple[str, str, str, float]] = [
            ("ingest_tool", "OrchestratorAgent", "document must be normalized before agent planning", 0.32),
            ("profile_tool", "OrchestratorAgent", "document domain profile informs downstream KG extraction", 0.18),
            ("segment_tool", "OrchestratorAgent", "segment boundaries are required for evidence-scoped KG tools", 0.22),
        ]
        for tool_name, agent_name, reason, eig in mandatory:
            if tool_name not in completed:
                tool = self.tools[tool_name]
                return AgentProposal.from_scores(
                    agent_name=agent_name,
                    proposed_action=tool_name,
                    expected_information_gain_value=eig,
                    risk=0.02,
                    cost=tool.cost,
                    reason=reason,
                )

        if "validate_tool" in completed and "candidate_store_tool" not in completed:
            tool = self.tools["candidate_store_tool"]
            return AgentProposal.from_scores(
                agent_name="OrchestratorAgent",
                proposed_action="candidate_store_tool",
                expected_information_gain_value=0.12,
                risk=0.03,
                cost=tool.cost,
                reason="validated candidate objects should be persisted before governance actions",
            )

        return None

    def _collect_proposals(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
    ) -> list[AgentProposal]:
        completed = _completed_tools(state)
        proposals: list[AgentProposal] = []
        for agent in self.agents:
            proposals.extend(agent.propose(state, uncertainty, completed))
        return [item for item in proposals if item.proposed_action in self.tools]

    def _low_gain_stop(self, state: GraphState, proposal: AgentProposal) -> bool:
        budget = _budget(state)
        if proposal.utility >= float(budget["min_utility"]):
            self._low_eig_rounds = 0
            return False
        self._low_eig_rounds += 1
        if self._low_eig_rounds < int(budget["max_low_eig_rounds"]):
            return False
        state["status"] = _candidate_or_quarantine(state)
        state.setdefault("warnings", []).append(
            "agent stopped because expected information gain stayed below threshold"
        )
        return True

    def _record_trace(
        self,
        state: GraphState,
        proposal: AgentProposal,
        proposals: list[AgentProposal],
        uncertainty: dict[str, float],
        metrics: dict[str, float],
        pub_conf: float,
    ) -> None:
        trace = {
            **proposal.to_dict(),
            "selected_action": proposal.proposed_action,
            "candidate_actions": [item.to_dict() for item in proposals],
            "uncertainty_scores": uncertainty,
            "graph_quality_metrics": metrics,
            "publish_confidence": pub_conf,
            "step_index": len(state.get("agent_trace", [])) + 1,
        }
        state.setdefault("agent_trace", []).append(trace)

    def _execute_tool(
        self,
        state: GraphState,
        proposal: AgentProposal,
        on_node: NodeCallback | None = None,
    ) -> None:
        tool = self.tools[proposal.proposed_action]
        if proposal.proposed_action == "registry_finalize_tool":
            _downgrade_unpublished_agentic_publish(state)
        run_tool_with_audit(state, tool, step_index=self._step_index)
        self._step_index += 1
        self._save_checkpoint(state, tool.node_name)
        if on_node is not None:
            on_node(tool.node_name)

    def _should_stop(self, state: GraphState) -> bool:
        completed = _completed_tools(state)
        return "registry_finalize_tool" in completed

    def _budget_stop(self, state: GraphState) -> None:
        state["status"] = _candidate_or_quarantine(state)
        state.setdefault("warnings", []).append("agent budget exhausted")

    def _no_action_stop(self, state: GraphState) -> None:
        state["status"] = _candidate_or_quarantine(state)
        state.setdefault("warnings", []).append("agent stopped because no useful next action was available")

    def _ensure_registry_finalized(
        self,
        state: GraphState,
        on_node: NodeCallback | None = None,
    ) -> None:
        completed = _completed_tools(state)
        if "registry_finalize_tool" in completed:
            return
        if not state.get("policy_decisions") and "policy_tool" in self.tools and "critic_tool" in completed:
            proposal = AgentProposal.from_scores(
                agent_name="PolicyAgent",
                proposed_action="policy_tool",
                expected_information_gain_value=0.1,
                risk=0.08,
                cost=self.tools["policy_tool"].cost,
                reason="final policy decision is needed before registry finalization",
            )
            self._record_trace(
                state,
                proposal,
                [proposal],
                summarize_uncertainty(state),
                graph_metrics(state),
                publish_confidence(state),
            )
            self._execute_tool(state, proposal, on_node=on_node)

        proposal = AgentProposal.from_scores(
            agent_name="OrchestratorAgent",
            proposed_action="registry_finalize_tool",
            expected_information_gain_value=0.05,
            risk=0.02,
            cost=self.tools["registry_finalize_tool"].cost,
            reason="agent run complete; persist audit, policy, quarantine, and schema state",
        )
        self._record_trace(
            state,
            proposal,
            [proposal],
            summarize_uncertainty(state),
            graph_metrics(state),
            publish_confidence(state),
        )
        self._execute_tool(state, proposal, on_node=on_node)

    def _save_checkpoint(self, state: GraphState, node_name: str) -> None:
        if self.checkpoint_store is None:
            return
        state["checkpoint_path"] = str(self.checkpoint_store.db_path)
        self.checkpoint_store.put_checkpoint(
            state,
            node_name=node_name,
            step_index=self._step_index,
        )


def _completed_tools(state: GraphState) -> set[str]:
    return {
        str(item.get("selected_action", ""))
        for item in state.get("agent_trace", [])
        if item.get("selected_action")
    }


def _budget(state: GraphState) -> dict[str, float | int]:
    budget = dict(DEFAULT_AGENT_BUDGET)
    budget.update(state.get("agent_budget", {}))
    return budget


def _candidate_or_quarantine(state: GraphState) -> str:
    metrics = graph_metrics(state)
    if metrics["evidence_coverage"] < 0.5 or metrics["conflict_score"] > 0.5:
        return "quarantined"
    return "candidate"


def _active_questions(metrics: dict[str, float]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    if metrics["evidence_coverage"] < 1.0:
        questions.append({
            "question": "Which claims still need source evidence?",
            "reason": "evidence_coverage_below_one",
            "score": round(1.0 - metrics["evidence_coverage"], 4),
        })
    if metrics["graph_sparse_penalty"] > 0.0:
        questions.append({
            "question": "Which entity pairs need relation evidence?",
            "reason": "graph_is_sparse",
            "score": metrics["graph_sparse_penalty"],
        })
    if metrics["conflict_score"] > 0.0:
        questions.append({
            "question": "Which subject-predicate pairs have conflicting objects?",
            "reason": "relation_conflict_detected",
            "score": metrics["conflict_score"],
        })
    return questions


def _downgrade_unpublished_agentic_publish(state: GraphState) -> None:
    completed = _completed_tools(state)
    decisions = state.get("policy_decisions", [])
    if "publish_tool" in completed or not decisions:
        return
    decision = decisions[0]
    if decision.get("action") != "publish":
        return
    decision["action"] = "candidate"
    reasons = list(decision.get("reasons", []))
    reasons.append("agentic_publish_confidence_below_threshold")
    decision["reasons"] = reasons
    decision["publish_confidence"] = publish_confidence(state)
    state["status"] = "candidate"
