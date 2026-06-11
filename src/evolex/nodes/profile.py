from __future__ import annotations

from evolex.graph.state import GraphState


DOMAIN_KEYWORDS = {
    "software_systems": ("api", "service", "database", "cache", "queue", "pipeline"),
    "operations": ("deployment", "rollback", "monitoring", "alert", "incident", "slo"),
    "measurement": ("latency", "throughput", "temperature", "voltage", "resistance", "error rate"),
    "modeling": ("model", "schema", "ontology", "embedding", "evaluation", "dataset"),
}


def profile_node(state: GraphState) -> dict:
    text = state.get("document_text", "")
    lowered = text.lower()
    domains = [
        domain
        for domain, keywords in DOMAIN_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]

    if not domains:
        domains = ["technical_general"]

    return {
        "document_type": "technical_note",
        "domains": domains,
    }
