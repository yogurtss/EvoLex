from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ProposalType = Literal["new_type", "new_relation", "new_attribute", "type_merge", "type_split"]


@dataclass
class SchemaProposal:
    """A proposal for a schema change detected from document evidence."""

    proposal_id: str
    proposal_type: ProposalType
    name: str
    description: str = ""
    supporting_texts: list[str] = field(default_factory=list)
    evidence_spans: list[str] = field(default_factory=list)
    occurrence_count: int = 1
    independent_document_count: int = 1
    relation_pattern_consistency: float = 0.0
    evidence_coverage: float = 0.0
    source_run_ids: list[str] = field(default_factory=list)
    schema_version: str = ""


def schema_proposal_to_dict(p: SchemaProposal) -> dict:
    return {
        "proposal_id": p.proposal_id,
        "proposal_type": p.proposal_type,
        "name": p.name,
        "description": p.description,
        "supporting_texts": p.supporting_texts,
        "evidence_spans": p.evidence_spans,
        "occurrence_count": p.occurrence_count,
        "independent_document_count": p.independent_document_count,
        "relation_pattern_consistency": p.relation_pattern_consistency,
        "evidence_coverage": p.evidence_coverage,
        "source_run_ids": p.source_run_ids,
        "schema_version": p.schema_version,
    }


def dict_to_schema_proposal(d: dict) -> SchemaProposal:
    return SchemaProposal(
        proposal_id=d.get("proposal_id", ""),
        proposal_type=d.get("proposal_type", "new_type"),
        name=d.get("name", ""),
        description=d.get("description", ""),
        supporting_texts=list(d.get("supporting_texts", [])),
        evidence_spans=list(d.get("evidence_spans", [])),
        occurrence_count=int(d.get("occurrence_count", 1)),
        independent_document_count=int(d.get("independent_document_count", 1)),
        relation_pattern_consistency=float(d.get("relation_pattern_consistency", 0.0)),
        evidence_coverage=float(d.get("evidence_coverage", 0.0)),
        source_run_ids=list(d.get("source_run_ids", [])),
        schema_version=d.get("schema_version", ""),
    )
