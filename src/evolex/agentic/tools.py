from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from evolex.agents.deepseek_client import BaseExtractor
from evolex.graph.state import GraphState
from evolex.nodes.candidate_store import make_candidate_store_node
from evolex.nodes.critic import critic_node
from evolex.nodes.entity_merge import entity_merge_node
from evolex.nodes.entity_resolve import entity_resolve_node
from evolex.nodes.evolution import (
    evolution_consensus_node,
    evolution_shadow_node,
    make_evolution_commit_node,
    make_evolution_plan_node,
)
from evolex.nodes.extract import make_extract_node
from evolex.nodes.ingest import ingest_node
from evolex.nodes.policy_node import policy_node
from evolex.nodes.profile import profile_node
from evolex.nodes.publish import make_publish_node
from evolex.nodes.quality_review import make_quality_review_node
from evolex.nodes.relation_extract import make_relation_extract_node
from evolex.nodes.relation_merge import relation_merge_node
from evolex.nodes.registry_finalize import make_registry_finalize_node
from evolex.nodes.schema_gap import make_schema_gap_node
from evolex.nodes.schema_proposer import schema_proposer_node
from evolex.nodes.segment import segment_node
from evolex.nodes.validate import validate_node

NodeFunc = Callable[[GraphState], dict]


@dataclass(frozen=True)
class AgentTool:
    name: str
    node_name: str
    func: NodeFunc
    cost: float = 1.0

    def run(self, state: GraphState) -> dict:
        return self.func(state)


def build_agent_tools(
    extractor: BaseExtractor,
    output_dir: Path | None,
) -> dict[str, AgentTool]:
    schema_dir = (output_dir / "schema_candidates") if output_dir else None
    return {
        "ingest_tool": AgentTool("ingest_tool", "ingest", ingest_node, cost=0.2),
        "profile_tool": AgentTool("profile_tool", "profile", profile_node, cost=0.2),
        "segment_tool": AgentTool("segment_tool", "segment", segment_node, cost=0.2),
        "extract_tool": AgentTool("extract_tool", "extract", make_extract_node(extractor), cost=1.2),
        "validate_tool": AgentTool("validate_tool", "validate", validate_node, cost=0.3),
        "candidate_store_tool": AgentTool(
            "candidate_store_tool",
            "candidate_store",
            make_candidate_store_node(output_dir),
            cost=0.4,
        ),
        "entity_resolve_tool": AgentTool(
            "entity_resolve_tool",
            "entity_resolve",
            entity_resolve_node,
            cost=0.7,
        ),
        "entity_merge_tool": AgentTool(
            "entity_merge_tool",
            "entity_merge",
            entity_merge_node,
            cost=0.5,
        ),
        "relation_extract_tool": AgentTool(
            "relation_extract_tool",
            "relation_extract",
            make_relation_extract_node(extractor),
            cost=1.0,
        ),
        "relation_merge_tool": AgentTool(
            "relation_merge_tool",
            "relation_merge",
            relation_merge_node,
            cost=0.5,
        ),
        "evolution_plan_tool": AgentTool(
            "evolution_plan_tool",
            "evolution_plan",
            make_evolution_plan_node(output_dir),
            cost=0.7,
        ),
        "evolution_shadow_tool": AgentTool(
            "evolution_shadow_tool",
            "evolution_shadow",
            evolution_shadow_node,
            cost=0.8,
        ),
        "evolution_consensus_tool": AgentTool(
            "evolution_consensus_tool",
            "evolution_consensus",
            evolution_consensus_node,
            cost=0.5,
        ),
        "evolution_commit_tool": AgentTool(
            "evolution_commit_tool",
            "evolution_commit",
            make_evolution_commit_node(output_dir),
            cost=0.8,
        ),
        "schema_gap_tool": AgentTool(
            "schema_gap_tool",
            "schema_gap",
            make_schema_gap_node(schema_dir),
            cost=0.5,
        ),
        "schema_proposer_tool": AgentTool(
            "schema_proposer_tool",
            "schema_proposer",
            schema_proposer_node,
            cost=0.7,
        ),
        "quality_review_tool": AgentTool(
            "quality_review_tool",
            "quality_review",
            make_quality_review_node(),
            cost=0.5,
        ),
        "critic_tool": AgentTool("critic_tool", "critic", critic_node, cost=0.5),
        "policy_tool": AgentTool("policy_tool", "policy", policy_node, cost=0.3),
        "publish_tool": AgentTool("publish_tool", "publish", make_publish_node(output_dir), cost=0.6),
        "registry_finalize_tool": AgentTool(
            "registry_finalize_tool",
            "registry_finalize",
            make_registry_finalize_node(output_dir),
            cost=0.4,
        ),
    }


def run_tool_with_audit(
    state: GraphState,
    tool: AgentTool,
    *,
    step_index: int,
) -> None:
    status_before = state.get("status")
    warnings_before = list(state.get("warnings", []))
    start = perf_counter()
    update = tool.run(state)
    elapsed = perf_counter() - start
    state.update(update)
    state["tool_call_count"] = int(state.get("tool_call_count", 0)) + 1
    warnings_after = list(state.get("warnings", []))
    new_warnings = warnings_after[len(warnings_before):]
    state.setdefault("audit_events", []).append(
        {
            "node_name": tool.node_name,
            "status_before": status_before,
            "status_after": state.get("status"),
            "decision": _policy_decision(state, tool.node_name),
            "warnings": ", ".join(str(item) for item in new_warnings),
            "elapsed_seconds": elapsed,
            "agent_step_index": step_index,
        }
    )


def _policy_decision(state: GraphState, node_name: str) -> str | None:
    if node_name != "policy":
        return None
    decisions = state.get("policy_decisions", [])
    if not decisions:
        return None
    return str(decisions[0].get("action", ""))
