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
from evolex.agentic.metrics import graph_metrics, publish_confidence, publish_gate
from evolex.agentic.tools import build_agent_tools, run_tool_with_audit
from evolex.agents.deepseek_client import BaseExtractor, LLMConfig, get_default_extractor
from evolex.graph.state import GraphState
from evolex.repositories.evaluation import CheckpointStore

NodeCallback = Callable[[str], None]
GraphLogCallback = Callable[[str, str], None]


DEFAULT_AGENT_BUDGET = {
    "max_rounds": 40,
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

    def invoke(
        self,
        initial_state: GraphState,
        on_node: NodeCallback | None = None,
    ) -> GraphState:
        state: GraphState = dict(initial_state)
        state.setdefault("agent_trace", [])
        state.setdefault("agent_budget", dict(DEFAULT_AGENT_BUDGET))
        state.setdefault("active_questions", [])
        state.setdefault("low_eig_rounds", 0)
        if "completed_tools" not in state:
            state["completed_tools"] = sorted(
                {
                    str(item.get("selected_action", ""))
                    for item in state.get("agent_trace", [])
                    if item.get("selected_action")
                }
            )
        state["completed_tools"] = _reconcile_completed_tools(state)

        while not self._should_stop(state):
            budget = _budget(state)
            if len(state.get("agent_trace", [])) >= int(budget["max_rounds"]):
                if state.get("status") != "published":
                    self._budget_stop(state)
                else:
                    state.setdefault("warnings", []).append(
                        "agent proposal budget reached after publication; "
                        "registry finalization continued as a safety operation"
                    )
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
        return [
            item
            for item in proposals
            if item.proposed_action in self.tools
            and _tool_execution_allowed(state, item.proposed_action)[0]
        ]

    def _low_gain_stop(self, state: GraphState, proposal: AgentProposal) -> bool:
        budget = _budget(state)
        if proposal.utility >= float(budget["min_utility"]):
            state["low_eig_rounds"] = 0
            return False
        low_eig_rounds = int(state.get("low_eig_rounds", 0)) + 1
        state["low_eig_rounds"] = low_eig_rounds
        if low_eig_rounds < int(budget["max_low_eig_rounds"]):
            return False
        if state.get("status") != "published":
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
        allowed, reason = _tool_execution_allowed(
            state,
            proposal.proposed_action,
        )
        if not allowed:
            state.setdefault("warnings", []).append(
                f"blocked tool {proposal.proposed_action}: {reason}"
            )
            if state.get("status") != "published":
                state["status"] = "quarantined"
            raise RuntimeError(
                f"agent tool dependency gate blocked "
                f"{proposal.proposed_action}: {reason}"
            )
        invalidated = _prepare_tool_execution(state, proposal.proposed_action)
        if (
            state.get("agent_trace")
            and state["agent_trace"][-1].get("selected_action")
            == proposal.proposed_action
        ):
            state["agent_trace"][-1]["tool_revision"] = state.get(
                "tool_revisions", {}
            ).get(proposal.proposed_action, 1)
            state["agent_trace"][-1]["invalidated_downstream_tools"] = sorted(
                invalidated
            )
        run_tool_with_audit(state, tool, step_index=self._step_index)
        completed_tools = list(state.get("completed_tools", []))
        if proposal.proposed_action not in completed_tools:
            completed_tools.append(proposal.proposed_action)
        state["completed_tools"] = completed_tools
        _update_policy_outcomes(state, proposal.proposed_action)
        self._step_index += 1
        self._save_checkpoint(state, tool.node_name)
        if on_node is not None:
            on_node(tool.node_name)

    def _should_stop(self, state: GraphState) -> bool:
        completed = _completed_tools(state)
        return "registry_finalize_tool" in completed

    def _budget_stop(self, state: GraphState) -> None:
        if state.get("status") != "published":
            state["status"] = _candidate_or_quarantine(state)
        state.setdefault("warnings", []).append("agent budget exhausted")

    def _no_action_stop(self, state: GraphState) -> None:
        if state.get("status") != "published":
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
        if not state.get("policy_decisions"):
            if "policy_tool" in self.tools and "critic_tool" in completed:
                proposal = AgentProposal.from_scores(
                    agent_name="PolicyAgent",
                    proposed_action="policy_tool",
                    expected_information_gain_value=0.1,
                    risk=0.08,
                    cost=self.tools["policy_tool"].cost,
                    reason="final policy decision is needed before registry finalization",
                )
                if _trace_budget_available(state):
                    self._record_trace(
                        state,
                        proposal,
                        [proposal],
                        summarize_uncertainty(state),
                        graph_metrics(state),
                        publish_confidence(state),
                    )
                self._execute_tool(state, proposal, on_node=on_node)
                completed = _completed_tools(state)
            else:
                state["governance_incomplete"] = True
                state["status"] = "quarantined"
                state["policy_decisions"] = [
                    {
                        "action": "quarantine",
                        "policy_engine_action": "not_evaluated",
                        "canonical_action": "held",
                        "delivery_action": "quarantined",
                        "risk_level": "high",
                        "reasons": ["incomplete_agent_dependency_chain"],
                    }
                ]
                state.setdefault("warnings", []).append(
                    "agent run finalized as quarantined because the policy "
                    "dependency chain did not complete"
                )

        proposal = AgentProposal.from_scores(
            agent_name="OrchestratorAgent",
            proposed_action="registry_finalize_tool",
            expected_information_gain_value=0.05,
            risk=0.02,
            cost=self.tools["registry_finalize_tool"].cost,
            reason="agent run complete; persist audit, policy, quarantine, and schema state",
        )
        if _trace_budget_available(state):
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
    if "completed_tools" in state:
        completed = {
            str(item)
            for item in state.get("completed_tools", [])
            if str(item)
        }
    else:
        completed = {
            str(item.get("selected_action", ""))
            for item in state.get("agent_trace", [])
            if item.get("selected_action")
        }
    return completed - set(state.get("invalidated_tools", []))


def _reconcile_completed_tools(state: GraphState) -> list[str]:
    """Drop stale completion markers whose materialized output was removed."""
    completed = {
        str(item)
        for item in state.get("completed_tools", [])
        if str(item)
    }
    trace_actions = {
        str(item.get("selected_action", ""))
        for item in state.get("agent_trace", [])
        if item.get("selected_action")
    }
    reconciled: set[str] = set()
    for tool_name in completed:
        output_fields = TOOL_OUTPUT_FIELDS.get(tool_name, ())
        if output_fields and not any(field in state for field in output_fields):
            continue
        if not output_fields and tool_name not in trace_actions:
            continue
        reconciled.add(tool_name)
    return sorted(reconciled)


TOOL_DEPENDENCIES: dict[str, set[str]] = {
    "profile_tool": {"ingest_tool"},
    "segment_tool": {"ingest_tool", "profile_tool"},
    "extract_tool": {"segment_tool"},
    "validate_tool": {"extract_tool"},
    "candidate_store_tool": {"validate_tool"},
    "entity_resolve_tool": {"validate_tool", "candidate_store_tool"},
    "entity_merge_tool": {"entity_resolve_tool"},
    "relation_extract_tool": {"entity_merge_tool"},
    "relation_merge_tool": {"relation_extract_tool"},
    "schema_gap_tool": {"relation_merge_tool"},
    "schema_proposer_tool": {"schema_gap_tool"},
    "evolution_plan_tool": {"relation_merge_tool", "schema_gap_tool"},
    "evolution_shadow_tool": {"evolution_plan_tool"},
    "evolution_consensus_tool": {"evolution_shadow_tool"},
    "quality_review_tool": {"relation_merge_tool", "evolution_consensus_tool"},
    "critic_tool": {"quality_review_tool"},
    "policy_tool": {"critic_tool", "evolution_consensus_tool"},
    "publish_tool": {"policy_tool", "evolution_commit_tool"},
    "evolution_commit_tool": {
        "policy_tool",
        "evolution_consensus_tool",
    },
    "registry_finalize_tool": {
        "policy_tool",
        "publish_tool",
        "evolution_commit_tool",
    },
}


def _tool_execution_allowed(
    state: GraphState,
    tool_name: str,
) -> tuple[bool, str]:
    """Enforce the workflow independently of potentially untrusted agents."""
    completed = _completed_tools(state)

    if tool_name == "registry_finalize_tool":
        if state.get("governance_incomplete") and state.get("policy_decisions"):
            return True, ""
        if "policy_tool" not in completed:
            return False, "policy_tool has not completed"
        decisions = state.get("policy_decisions", [])
        action = str(decisions[0].get("action", "")) if decisions else ""
        if action != "publish":
            return True, ""
        if "publish_tool" in completed and state.get("status") == "published":
            return True, ""
        gate_passed, _, _ = publish_gate(state)
        commit_status = str(state.get("evolution_commit", {}).get("status", ""))
        if not gate_passed or commit_status in {
            "failed",
            "held",
            "shadow_only",
        }:
            return True, ""
        return (
            False,
            "an authorized publish must finish canonical commit and delivery "
            "before registry finalization",
        )

    missing = TOOL_DEPENDENCIES.get(tool_name, set()) - completed
    if missing:
        return False, f"missing prerequisites: {', '.join(sorted(missing))}"

    if (
        tool_name == "evolution_plan_tool"
        and state.get("unresolved_terms")
        and "schema_proposer_tool" not in completed
    ):
        return False, "schema_proposer_tool is required for unresolved schema terms"

    if tool_name == "evolution_commit_tool":
        decisions = state.get("policy_decisions", [])
        action = str(decisions[0].get("action", "")) if decisions else ""
        gate_passed, _, _ = publish_gate(state)
        if action != "publish":
            return False, "policy does not authorize publish"
        if not state.get("evolution_decision", {}).get("accepted"):
            return False, "evolution consensus did not accept the patch"
        if not gate_passed:
            return False, "pre-commit publication confidence gate did not pass"

    if tool_name == "publish_tool":
        decisions = state.get("policy_decisions", [])
        action = str(decisions[0].get("action", "")) if decisions else ""
        gate_passed, _, _ = publish_gate(state)
        if action != "publish":
            return False, "policy does not authorize publish"
        if state.get("evolution_commit", {}).get("status") != "committed":
            return False, "canonical evolution commit has not completed"
        if not state.get("evolution_decision", {}).get("accepted"):
            return False, "evolution consensus did not accept the patch"
        if not gate_passed:
            return False, "publication confidence gate did not pass"

    return True, ""


TOOL_OUTPUT_FIELDS: dict[str, tuple[str, ...]] = {
    "validate_tool": ("validation_results",),
    "candidate_store_tool": ("candidate_output_path",),
    "entity_resolve_tool": (
        "entities",
        "entity_decisions",
        "mention_entity_map",
    ),
    "entity_merge_tool": (
        "entity_merge_proposals",
        "merge_decisions",
    ),
    "relation_extract_tool": (
        "relations",
        "relation_extraction_mode",
        "joint_relation_yield",
        "relation_endpoint_failures",
    ),
    "relation_merge_tool": (
        "relation_merge_proposals",
        "relation_identity_hypotheses",
        "relation_conflicts",
    ),
    "schema_gap_tool": ("unresolved_terms", "active_schema"),
    "schema_proposer_tool": ("schema_proposals",),
    "evolution_plan_tool": (
        "canonical_baseline",
        "graph_patch",
        "canonical_entity_map",
    ),
    "evolution_shadow_tool": ("shadow_evaluation",),
    "evolution_consensus_tool": ("evolution_decision",),
    "quality_review_tool": ("quality_scores",),
    "critic_tool": ("critic_results",),
    "policy_tool": ("policy_decisions",),
    "publish_tool": ("publish_output_path",),
    "evolution_commit_tool": (
        "evolution_commit",
        "canonical_store_path",
        "canonical_version_id",
    ),
    "registry_finalize_tool": ("registry_output_path",),
}


def _prepare_tool_execution(
    state: GraphState,
    tool_name: str,
) -> set[str]:
    """Invalidate every previously computed descendant before a tool reruns."""
    descendants = _tool_descendants(tool_name)
    invalidated = set(state.get("invalidated_tools", []))
    invalidated.update(descendants)
    invalidated.discard(tool_name)
    state["invalidated_tools"] = sorted(invalidated)
    revisions = dict(state.get("tool_revisions", {}))
    revisions[tool_name] = int(revisions.get(tool_name, 0)) + 1
    state["tool_revisions"] = revisions
    for descendant in descendants:
        for field in TOOL_OUTPUT_FIELDS.get(descendant, ()):
            state.pop(field, None)
    return descendants


def _tool_descendants(tool_name: str) -> set[str]:
    descendants: set[str] = set()
    frontier = [tool_name]
    while frontier:
        current = frontier.pop()
        for candidate, dependencies in TOOL_DEPENDENCIES.items():
            if current not in dependencies or candidate in descendants:
                continue
            descendants.add(candidate)
            frontier.append(candidate)
    return descendants


def _budget(state: GraphState) -> dict[str, float | int]:
    budget = dict(DEFAULT_AGENT_BUDGET)
    budget.update(state.get("agent_budget", {}))
    return budget


def _trace_budget_available(state: GraphState) -> bool:
    return len(state.get("agent_trace", [])) < int(_budget(state)["max_rounds"])


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
    decision.setdefault("policy_engine_action", "publish")
    commit_status = state.get("evolution_commit", {}).get("status")
    commit_failed = commit_status == "failed"
    canonical_committed = commit_status == "committed"
    decision["action"] = "quarantine" if commit_failed else "candidate"
    decision["canonical_action"] = (
        "committed" if canonical_committed else "held"
    )
    decision["delivery_action"] = (
        "quarantined" if commit_failed else "candidate"
    )
    reasons = list(decision.get("reasons", []))
    reasons.append(
        "canonical_evolution_commit_failed"
        if commit_failed
        else (
            "canonical_committed_delivery_not_published"
            if canonical_committed
            else "pre_commit_publish_confidence_gate_failed"
        )
    )
    decision["reasons"] = reasons
    decision["publish_confidence"] = publish_confidence(state)
    state["status"] = "quarantined" if commit_failed else "candidate"


def _update_policy_outcomes(state: GraphState, tool_name: str) -> None:
    decisions = state.get("policy_decisions", [])
    if not decisions:
        return
    decision = decisions[0]
    decision.setdefault(
        "policy_engine_action", decision.get("action", "candidate")
    )
    if tool_name == "evolution_commit_tool":
        commit_status = state.get("evolution_commit", {}).get("status")
        decision["canonical_action"] = (
            "committed" if commit_status == "committed" else "held"
        )
    elif tool_name == "publish_tool":
        decision["delivery_action"] = (
            "published"
            if state.get("status") == "published"
            else state.get("status", "candidate")
        )
