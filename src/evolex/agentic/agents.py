from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from evolex.agentic.math import action_utility, expected_information_gain
from evolex.agentic.metrics import graph_metrics, publish_gate
from evolex.graph.state import GraphState


@dataclass(frozen=True)
class AgentProposal:
    agent_name: str
    proposed_action: str
    expected_information_gain: float
    risk: float
    cost: float
    reason: str
    tool_args: dict[str, Any]
    utility: float

    @classmethod
    def from_scores(
        cls,
        *,
        agent_name: str,
        proposed_action: str,
        expected_information_gain_value: float,
        risk: float,
        cost: float,
        reason: str,
        tool_args: dict[str, Any] | None = None,
    ) -> "AgentProposal":
        return cls(
            agent_name=agent_name,
            proposed_action=proposed_action,
            expected_information_gain=round(expected_information_gain_value, 4),
            risk=round(risk, 4),
            cost=round(cost, 4),
            reason=reason,
            tool_args=tool_args or {},
            utility=round(
                action_utility(
                    expected_information_gain_value,
                    cost=cost,
                    risk=risk,
                ),
                4,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "proposed_action": self.proposed_action,
            "expected_information_gain": self.expected_information_gain,
            "risk": self.risk,
            "cost": self.cost,
            "reason": self.reason,
            "tool_args": self.tool_args,
            "utility": self.utility,
        }


class KGAgent(Protocol):
    name: str

    def propose(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
        completed_tools: set[str],
    ) -> list[AgentProposal]:
        raise NotImplementedError


class ExtractionAgent:
    name = "ExtractionAgent"

    def propose(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
        completed_tools: set[str],
    ) -> list[AgentProposal]:
        if "extract_tool" not in completed_tools:
            eig = expected_information_gain(uncertainty["state_uncertainty"], 0.55)
            return [
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="extract_tool",
                    expected_information_gain_value=max(eig, 0.36),
                    risk=0.08,
                    cost=1.2,
                    reason="initial candidate KG extraction has not run",
                )
            ]
        return []


class EntityResolutionAgent:
    name = "EntityResolutionAgent"

    def propose(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
        completed_tools: set[str],
    ) -> list[AgentProposal]:
        if "extract_tool" not in completed_tools or "entity_resolve_tool" in completed_tools:
            return []
        mentions = len(state.get("mentions", []))
        atoms = len(state.get("semantic_atoms", []))
        if mentions or atoms:
            eig = expected_information_gain(uncertainty["entity_uncertainty"], 0.35)
            return [
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="entity_resolve_tool",
                    expected_information_gain_value=max(eig, 0.28),
                    risk=0.12,
                    cost=0.7,
                    reason="mentions or atoms are available but canonical entities are not resolved",
                )
            ]
        return []


class CanonicalizationAgent:
    """Canonicalize identity hypotheses while preserving reversible lineage."""

    name = "CanonicalizationAgent"

    def propose(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
        completed_tools: set[str],
    ) -> list[AgentProposal]:
        proposals: list[AgentProposal] = []
        if (
            "entity_resolve_tool" in completed_tools
            and "entity_merge_tool" not in completed_tools
        ):
            proposals.append(
                AgentProposal.from_scores(
                    agent_name="EntityCanonicalizationAgent",
                    proposed_action="entity_merge_tool",
                    expected_information_gain_value=max(
                        uncertainty["entity_uncertainty"] - 0.3,
                        0.24,
                    ),
                    risk=0.14,
                    cost=0.5,
                    reason=(
                        "same-type entity identity hypotheses need evidence-constrained "
                        "canonicalization before relation endpoints are materialized"
                    ),
                )
            )
        if (
            "relation_extract_tool" in completed_tools
            and "relation_merge_tool" not in completed_tools
        ):
            proposals.append(
                AgentProposal.from_scores(
                    agent_name="RelationCanonicalizationAgent",
                    proposed_action="relation_merge_tool",
                    expected_information_gain_value=max(
                        uncertainty["relation_uncertainty"] - 0.35,
                        0.23,
                    ),
                    risk=0.12,
                    cost=0.5,
                    reason=(
                        "duplicate relation assertions and predicate aliases must be "
                        "merged without discarding their evidence lineage"
                    ),
                )
            )
        return proposals


class EvidenceAgent:
    name = "EvidenceAgent"

    def propose(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
        completed_tools: set[str],
    ) -> list[AgentProposal]:
        proposals: list[AgentProposal] = []
        if "extract_tool" in completed_tools and "validate_tool" not in completed_tools:
            eig = expected_information_gain(uncertainty["evidence_uncertainty"], 0.45)
            proposals.append(
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="validate_tool",
                    expected_information_gain_value=max(eig, 0.22),
                    risk=0.05,
                    cost=0.3,
                    reason="candidate claims need evidence-link validation",
                )
            )

        metrics = graph_metrics(state)
        if (
            "validate_tool" in completed_tools
            and metrics["evidence_coverage"] < 1.0
            and _tool_count(state, "extract_tool") < 2
        ):
            eig = 0.18 + (1.0 - metrics["evidence_coverage"]) * 0.3
            proposals.append(
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="extract_tool",
                    expected_information_gain_value=eig,
                    risk=0.15,
                    cost=1.2,
                    reason="evidence coverage is incomplete, so re-extraction may bind missing evidence",
                )
            )
        return proposals


class GraphCriticAgent:
    name = "GraphCriticAgent"

    def propose(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
        completed_tools: set[str],
    ) -> list[AgentProposal]:
        proposals: list[AgentProposal] = []
        metrics = graph_metrics(state)
        if (
            "entity_resolve_tool" in completed_tools
            and "relation_extract_tool" not in completed_tools
        ):
            eig = expected_information_gain(uncertainty["relation_uncertainty"], 0.4)
            merge_pending = "entity_merge_tool" not in completed_tools
            proposals.append(
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="relation_extract_tool",
                    expected_information_gain_value=(
                        0.04 if merge_pending else max(eig, 0.3)
                    ),
                    risk=0.5 if merge_pending else 0.12,
                    cost=1.2 if merge_pending else 1.0,
                    reason=(
                        "entity canonicalization should complete before relation endpoints "
                        "are materialized"
                        if merge_pending
                        else "resolved entities are available but graph edges have not been extracted"
                    ),
                )
            )

        if (
            "relation_extract_tool" in completed_tools
            and metrics["graph_sparse_penalty"] > 0.7
            and state.get("relation_extraction_mode") != "joint"
            and _tool_count(state, "relation_extract_tool") < 2
        ):
            proposals.append(
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="relation_extract_tool",
                    expected_information_gain_value=0.34,
                    risk=0.18,
                    cost=1.0,
                    reason="relations are sparse and another relation pass has positive expected gain",
                )
            )

        if (
            "relation_merge_tool" in completed_tools
            and "evolution_consensus_tool" in completed_tools
            and "quality_review_tool" not in completed_tools
        ):
            proposals.append(
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="quality_review_tool",
                    expected_information_gain_value=0.24,
                    risk=0.08,
                    cost=0.5,
                    reason="graph candidates need consistency, duplicate, and dangling-reference review",
                )
            )
        return proposals


class SchemaAgent:
    name = "SchemaAgent"

    def propose(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
        completed_tools: set[str],
    ) -> list[AgentProposal]:
        proposals: list[AgentProposal] = []
        if "relation_merge_tool" in completed_tools and "schema_gap_tool" not in completed_tools:
            proposals.append(
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="schema_gap_tool",
                    expected_information_gain_value=0.18,
                    risk=0.07,
                    cost=0.5,
                    reason="candidate graph should be checked against the active schema",
                )
            )
        if (
            "schema_gap_tool" in completed_tools
            and state.get("unresolved_terms")
            and "schema_proposer_tool" not in completed_tools
        ):
            proposals.append(
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="schema_proposer_tool",
                    expected_information_gain_value=max(uncertainty["schema_uncertainty"] - 0.35, 0.16),
                    risk=0.1,
                    cost=0.7,
                    reason="unresolved schema terms should become governed schema proposals",
                )
            )
        return proposals


class EvolutionAgent:
    """Stage, validate, and commit evidence-coupled graph patches."""

    name = "EvolutionAgent"

    def propose(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
        completed_tools: set[str],
    ) -> list[AgentProposal]:
        proposals: list[AgentProposal] = []
        schema_ready = (
            "schema_gap_tool" in completed_tools
            and (
                not state.get("unresolved_terms")
                or "schema_proposer_tool" in completed_tools
            )
        )
        if (
            "relation_merge_tool" in completed_tools
            and schema_ready
            and "evolution_plan_tool" not in completed_tools
        ):
            proposals.append(
                AgentProposal.from_scores(
                    agent_name="EvolutionPlanningAgent",
                    proposed_action="evolution_plan_tool",
                    expected_information_gain_value=0.31,
                    risk=0.08,
                    cost=0.7,
                    reason=(
                        "canonical entities and relations must become evidence-scoped "
                        "patch atoms before any persistent graph change"
                    ),
                )
            )
        if (
            "evolution_plan_tool" in completed_tools
            and "evolution_shadow_tool" not in completed_tools
        ):
            proposals.append(
                AgentProposal.from_scores(
                    agent_name="ShadowValidationAgent",
                    proposed_action="evolution_shadow_tool",
                    expected_information_gain_value=0.34,
                    risk=0.05,
                    cost=0.8,
                    reason=(
                        "the evidence-derived impact domain must synthesize and run "
                        "shadow invariants before promotion"
                    ),
                )
            )
        if (
            "evolution_shadow_tool" in completed_tools
            and "evolution_consensus_tool" not in completed_tools
        ):
            proposals.append(
                AgentProposal.from_scores(
                    agent_name="EvolutionConsensusAgent",
                    proposed_action="evolution_consensus_tool",
                    expected_information_gain_value=0.28,
                    risk=0.04,
                    cost=0.5,
                    reason=(
                        "independent evidence, replay, non-interference, and invariant "
                        "votes are required for the compensated patch"
                    ),
                )
            )
        if (
            "policy_tool" in completed_tools
            and _policy_action(state) == "publish"
            and "evolution_consensus_tool" in completed_tools
            and state.get("evolution_decision", {}).get("accepted")
            and "evolution_commit_tool" not in completed_tools
            and publish_gate(state)[0]
        ):
            proposals.append(
                AgentProposal.from_scores(
                    agent_name="EvolutionCommitAgent",
                    proposed_action="evolution_commit_tool",
                    expected_information_gain_value=0.16,
                    risk=0.06,
                    cost=0.8,
                    reason=(
                        "the policy-approved and shadow-validated patch must be "
                        "atomically committed to the canonical graph before the "
                        "run-level publication view is finalized"
                    ),
                )
            )
        return proposals


class PolicyAgent:
    name = "PolicyAgent"

    def propose(
        self,
        state: GraphState,
        uncertainty: dict[str, float],
        completed_tools: set[str],
    ) -> list[AgentProposal]:
        proposals: list[AgentProposal] = []
        if (
            "quality_review_tool" in completed_tools
            and "evolution_consensus_tool" in completed_tools
            and "critic_tool" not in completed_tools
        ):
            proposals.append(
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="critic_tool",
                    expected_information_gain_value=0.2,
                    risk=0.06,
                    cost=0.5,
                    reason="quality-reviewed claims need semantic evidence review",
                )
            )
        if "critic_tool" in completed_tools and "policy_tool" not in completed_tools:
            proposals.append(
                AgentProposal.from_scores(
                    agent_name=self.name,
                    proposed_action="policy_tool",
                    expected_information_gain_value=0.22,
                    risk=0.05,
                    cost=0.3,
                    reason="critic results and graph metrics are ready for governance routing",
                )
            )
        if "policy_tool" in completed_tools:
            action = _policy_action(state)
            if action == "publish" and "publish_tool" not in completed_tools:
                commit = state.get("evolution_commit", {})
                gate_passed, confidence, threshold = publish_gate(state)
                if "evolution_commit_tool" not in completed_tools:
                    if (
                        not gate_passed
                        and "registry_finalize_tool" not in completed_tools
                    ):
                        proposals.append(
                            AgentProposal.from_scores(
                                agent_name=self.name,
                                proposed_action="registry_finalize_tool",
                                expected_information_gain_value=0.1,
                                risk=max(0.0, 1.0 - confidence),
                                cost=0.4,
                                reason=(
                                    "pre-commit publish confidence gate failed: "
                                    f"{confidence:.4f} < {threshold:.4f}"
                                ),
                            )
                        )
                    return proposals
                if commit.get("status") != "committed":
                    proposals.append(
                        AgentProposal.from_scores(
                            agent_name=self.name,
                            proposed_action="registry_finalize_tool",
                            expected_information_gain_value=0.1,
                            risk=0.04,
                            cost=0.4,
                            reason=(
                                "canonical evolution was not committed; persist the "
                                "candidate or quarantine decision without publishing"
                            ),
                        )
                    )
                    return proposals
                metrics = graph_metrics(state)
                if gate_passed and metrics["graph_sparse_penalty"] <= 0.7:
                    proposals.append(
                        AgentProposal.from_scores(
                            agent_name=self.name,
                            proposed_action="publish_tool",
                            expected_information_gain_value=0.12,
                            risk=max(0.0, 1.0 - confidence),
                            cost=0.6,
                            reason="policy permits publishing and publish confidence is sufficient",
                        )
                    )
                elif "registry_finalize_tool" not in completed_tools:
                    proposals.append(
                        AgentProposal.from_scores(
                            agent_name=self.name,
                            proposed_action="registry_finalize_tool",
                            expected_information_gain_value=0.1,
                            risk=max(0.0, 1.0 - confidence),
                            cost=0.4,
                            reason="policy permits publishing, but agentic graph confidence is below the publish threshold",
                        )
                    )
            elif "registry_finalize_tool" not in completed_tools:
                proposals.append(
                    AgentProposal.from_scores(
                        agent_name=self.name,
                        proposed_action="registry_finalize_tool",
                        expected_information_gain_value=0.1,
                        risk=0.04,
                        cost=0.4,
                        reason="non-published run should finalize candidate, audit, and schema registries",
                    )
                )
        return proposals


def default_agents() -> list[KGAgent]:
    return [
        ExtractionAgent(),
        EntityResolutionAgent(),
        CanonicalizationAgent(),
        EvidenceAgent(),
        GraphCriticAgent(),
        SchemaAgent(),
        EvolutionAgent(),
        PolicyAgent(),
    ]


def choose_highest_utility(proposals: list[AgentProposal]) -> AgentProposal | None:
    if not proposals:
        return None
    return max(
        proposals,
        key=lambda item: (
            item.utility,
            item.expected_information_gain,
            -item.risk,
            -item.cost,
        ),
    )


def _tool_count(state: GraphState, tool_name: str) -> int:
    return sum(
        1
        for item in state.get("agent_trace", [])
        if item.get("selected_action") == tool_name
    )


def _policy_action(state: GraphState) -> str:
    decisions = state.get("policy_decisions", [])
    if not decisions:
        return ""
    return str(decisions[0].get("action", ""))
