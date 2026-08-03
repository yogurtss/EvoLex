from __future__ import annotations

from typing import Literal

RiskLevel = Literal["low", "medium", "high"]
PolicyAction = Literal["publish", "candidate", "quarantine", "reject"]


def assess_risk(signals: dict) -> RiskLevel:
    """Determine risk level from governance signals.

    Rules (from architecture doc §9.3):
    - Low: new instances, claims, aliases, supplemental evidence
    - Medium: new types, relations, attributes, domain/range extensions
    - High: type merge/split, parent changes, deletion, historical batch migration
    """
    # Hard rule: high-risk actions
    high_actions = {"type_merge", "type_split", "parent_change", "delete", "batch_migration"}
    if signals.get("change_type") in high_actions:
        return "high"

    # Medium-risk actions
    medium_actions = {"new_type", "new_relation", "new_attribute", "domain_range_ext"}
    if signals.get("change_type") in medium_actions:
        return "medium"

    # High evidence coverage signals lower risk
    evidence_coverage = float(signals.get("evidence_coverage", 0.0))
    if evidence_coverage < 0.5:
        return "medium"

    return "low"


def decide_policy(signals: dict) -> PolicyAction:
    """Determine the policy action from signals.

    Returns one of: publish, candidate, quarantine, reject.
    """
    # Hard reject for critical failures
    if signals.get("deterministic_violations"):
        return "reject"

    risk = assess_risk(signals)
    evidence_coverage = float(signals.get("evidence_coverage", 0.0))
    critic_approved = bool(signals.get("critic_approved", False))
    independent_docs = int(signals.get("independent_document_count", 0))

    # Reject if evidence is insufficient
    if evidence_coverage < 0.3:
        return "reject"

    # Quarantine if critic rejects or insufficient evidence
    if not critic_approved:
        return "quarantine"

    # Low risk with sufficient evidence → publish
    if risk == "low":
        if evidence_coverage >= 0.8 and independent_docs >= 1:
            return "publish"
        return "candidate"

    # Medium risk → candidate
    if risk == "medium":
        return "candidate"

    # High risk → quarantine
    return "quarantine"
