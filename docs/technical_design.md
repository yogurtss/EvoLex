# EvoLex Phase 1 Technical Design

## Purpose

EvoLex Phase 1 provides a small conversational CLI for processing technical
documents into candidate knowledge records. The system is domain-neutral by
default: software architecture notes, operations runbooks, hardware reports,
model evaluation notes, and semiconductor documents are all treated as technical
source material.

The goal of Phase 1 is not to publish a production knowledge graph. It creates a
controlled harness that can ingest text, segment it, extract semantic atoms,
validate their structure, and persist candidates for later review.

## Runtime Flow

```text
chat CLI
  -> intent classifier
  -> Phase 1 graph
  -> candidate JSONL output
```

The graph uses this fixed topology:

```text
START
  -> ingest
  -> profile
  -> segment
  -> extract
  -> validate
  -> candidate_store
  -> END
```

When `langgraph` is installed, the graph is built with `StateGraph`. When it is
not installed, the same node sequence runs through a local fallback runner so
tests and local demos stay deterministic.

## Agent Boundary

The agent is deliberately narrow in Phase 1. It can guide the user, identify
whether the input is text or a file path, run the graph, and summarize the run.
It does not have open-ended filesystem access, database access, or production KG
write permissions.

The extractor uses DeepSeek through an OpenAI-compatible chat completion API when
`DEEPSEEK_API_KEY` is set. Without that key, EvoLex uses a deterministic local
extractor for smoke tests.

## Language And KG Policy

Prompts are written in English.

KG-facing fields are normalized to English/ASCII:

- `type`
- `text`
- `kg_language`

The `evidence` field stores the original source span for traceability and may
preserve the source document language.

## General Technical Document Model

Phase 1 extracts small semantic atoms rather than a complete ontology. Typical
atoms include:

- named technical entities, such as services, APIs, models, schemas, or devices
- measurements, such as latency, voltage, throughput, duration, or error rate
- properties and claims, such as retry behavior, deployment constraints, or
  compatibility notes

Domain-specific ontologies should be added later as configuration or plugins,
not hard-coded into the Phase 1 harness.

## Candidate Output

Each JSONL record contains:

- `run_id`
- `document_id`
- `segment_id`
- `atom`
- `created_at`

Candidate records are intentionally isolated from any production knowledge graph.
Later phases can add entity resolution, schema governance, semantic critics,
policy decisions, and controlled publishing.
