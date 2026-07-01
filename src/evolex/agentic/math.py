from __future__ import annotations

import math
from typing import Any


def clamp_probability(value: float | int | None, default: float = 0.5) -> float:
    """Clamp a value into the probability interval used by entropy scoring."""
    if value is None:
        return default
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, probability))


def binary_entropy(probability: float | int | None) -> float:
    """Return normalized binary entropy in bits for a Bernoulli confidence."""
    p = clamp_probability(probability)
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def average_entropy(confidences: list[float]) -> float:
    if not confidences:
        return 1.0
    return sum(binary_entropy(value) for value in confidences) / len(confidences)


def expected_information_gain(current_entropy: float, expected_next_entropy: float) -> float:
    return max(0.0, float(current_entropy) - float(expected_next_entropy))


def action_utility(
    expected_information_gain_value: float,
    *,
    cost: float = 1.0,
    risk: float = 0.0,
    cost_weight: float = 0.08,
    risk_weight: float = 0.45,
) -> float:
    return (
        float(expected_information_gain_value)
        - cost_weight * float(cost)
        - risk_weight * float(risk)
    )


def confidence_posterior(
    prior: float,
    *,
    evidence_strength: float,
    conflict_strength: float = 0.0,
) -> float:
    """Lightweight Bayesian-style posterior update for explainable scoring.

    This is intentionally simple and deterministic: evidence contributes pseudo
    successes, conflicts contribute pseudo failures, and the prior contributes
    one pseudo observation on each side.
    """
    prior = clamp_probability(prior)
    evidence = max(0.0, float(evidence_strength))
    conflict = max(0.0, float(conflict_strength))
    alpha = 1.0 + prior + evidence
    beta = 1.0 + (1.0 - prior) + conflict
    return alpha / (alpha + beta)


def summarize_uncertainty(state: dict[str, Any]) -> dict[str, float]:
    entities = state.get("entities", [])
    relations = state.get("relations", [])
    claims = state.get("claim_candidates", [])
    schema_proposals = state.get("schema_proposals", [])

    entity_confidences = [
        clamp_probability(item.get("confidence", 0.5)) for item in entities
    ]
    relation_confidences = [
        clamp_probability(item.get("confidence", 0.5)) for item in relations
    ]
    claim_confidences = [
        clamp_probability(item.get("confidence", 0.5)) for item in claims
    ]
    schema_confidences = [
        confidence_posterior(
            0.45,
            evidence_strength=float(item.get("occurrence_count", 1)) / 3.0,
            conflict_strength=0.0 if item.get("status", "candidate") == "candidate" else 0.5,
        )
        for item in schema_proposals
    ]

    evidence_count = len(state.get("evidence_spans", []))
    claim_count = len(claims)
    evidence_coverage = min(1.0, evidence_count / max(claim_count, 1))
    evidence_support_score = confidence_posterior(
        0.5,
        evidence_strength=evidence_coverage,
        conflict_strength=max(0.0, 1.0 - evidence_coverage),
    )

    return {
        "entity_uncertainty": round(average_entropy(entity_confidences), 4),
        "relation_uncertainty": round(average_entropy(relation_confidences), 4),
        "claim_uncertainty": round(average_entropy(claim_confidences), 4),
        "schema_uncertainty": round(average_entropy(schema_confidences), 4),
        "evidence_uncertainty": round(binary_entropy(evidence_support_score), 4),
        "state_uncertainty": round(
            (
                average_entropy(entity_confidences)
                + average_entropy(relation_confidences)
                + average_entropy(claim_confidences)
                + average_entropy(schema_confidences)
                + binary_entropy(evidence_support_score)
            )
            / 5.0,
            4,
        ),
    }
