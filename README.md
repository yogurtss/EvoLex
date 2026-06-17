# EvoLex

EvoLex is a conversational CLI and controlled document-processing harness for
technical document knowledge extraction.

For a detailed architecture and implementation overview, see
[docs/technical_design.md](docs/technical_design.md).

By default EvoLex runs as one complete system: extract, validate, resolve
entities, review quality, apply policy, and publish structured knowledge.
The historical `phase1` / `phase2` / `phase3` names are still kept internally
for testing and debug compatibility, but the public CLI now treats the full
typed pipeline as the default runtime.

## System Pipeline

Internally the system still has stage boundaries. The old Phase 1 topology was:

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

The old Phase 2 topology appended publish to that chain:

```text
  ... -> candidate_store
  -> entity_resolve
  -> relation_extract
  -> quality_review
  -> publish
  -> END
```

The current unified system uses the Phase 3 topology with conditional routing:

```text
  ... -> extract
  -> validate
  -> entity_resolve
  -> relation_extract
  -> schema_gap           ← detects unmappable concepts
  -> schema_proposer      ← generates schema proposals
  -> quality_review
       │
       ▼  (conditional)
  ┌── critic  ── policy ──┐
  │                       │
  ▼                       ▼
quarantine            publish / candidate
```

| Node | What it does |
|------|-------------|
| `ingest` | Trims and validates raw document text |
| `profile` | Detects domain keywords, sets document type |
| `segment` | Splits text into sentence-boundary segments |
| `extract` | Produces typed objects (Claim, Evidence, Mention, Measurement, Condition) or legacy semantic atoms |
| `validate` | Validates object-level required fields; rejects Claims without Evidence |
| `entity_resolve` | Resolves mentions to entities with decision records (LINK / CREATE_CANDIDATE / AMBIGUOUS / REJECT) |
| `relation_extract` | Extracts relations between entities using LLM or heuristics |
| `schema_gap` | Identifies concepts that cannot be mapped to known schema types/predicates |
| `schema_proposer` | Generates new_type / new_relation / new_attribute proposals with supporting evidence |
| `quality_review` | Scores and filters atoms and relations |
| `critic` | Semantic review: verifies evidence sufficiency, flags inconsistencies |
| `policy` | Risk-based routing decision (publish / candidate / quarantine / reject) |
| `publish` | Writes approved objects to SQLite knowledge graph with audit trail |

## Environment

Create and activate the conda environment:

```bash
conda env create -f environment.yml
conda activate evolex
```

If you already created the environment and only need to refresh dependencies:

```bash
conda env update -f environment.yml --prune
```

Dependencies are declared in `pyproject.toml`. The conda environment installs the
project in editable mode with the `dev` extra.

### Rich (optional)

Install `rich` for styled terminal output, a live pipeline progress panel, and
intermediate model/node events:

```bash
pip install ".[rich]"
```

Without `rich`, the CLI falls back to plain-text output and no animations.

## LLM API

The extractor is LLM-first. By default it uses the DeepSeek OpenAI-compatible
chat API. DeepSeek keeps its provider-specific thinking parameters, while local
OpenAI-compatible models such as Qwen or a future Minimax endpoint use a generic
request body.

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

Runtime settings:

- `base_url`: `https://api.deepseek.com`
- `model`: `deepseek-v4-flash`
- `concurrency`: `4` segment-level extraction calls

You can override these settings when starting the CLI:

```bash
evolex chat \
  --llm-base-url https://api.deepseek.com \
  --llm-model deepseek-v4-flash \
  --llm-api-key "$DEEPSEEK_API_KEY" \
  --llm-concurrency 4
```

For a local OpenAI-compatible model, point EvoLex at the local server and set the
model name. Local generic endpoints on `localhost` / `127.0.0.1` do not require a
real API key:

```text
EvoLex> set llm url http://127.0.0.1:8000/v1
EvoLex> set llm model qwen3.5-397b
```

You can also inspect and change them inside the interactive CLI:

```text
EvoLex> llm settings
EvoLex> set llm url https://api.deepseek.com
EvoLex> set llm model deepseek-v4-flash
EvoLex> set llm api-key sk-...
EvoLex> set llm timeout 45
EvoLex> set llm concurrency 4
```

EvoLex parallelizes segment-level extraction calls up to the configured
concurrency. Relation extraction stays as a single aggregate call so it can use
the full resolved entity set.

The API path uses the official OpenAI SDK style:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("EVOLEX_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
```

EvoLex passes `reasoning_effort="high"` and
`extra_body={"thinking": {"type": "enabled"}}` only for the DeepSeek profile.
Generic OpenAI-compatible models receive only `model`, `messages`, and
`stream=False`.

Do not commit API keys. The repository intentionally reads the key only from the
environment.

If you need a forced no-network local debug run, set:

```bash
export EVOLEX_OFFLINE=1
```

Offline mode uses deterministic heuristic extractors. That path exists for
tests and local debugging; the main agent path is expected to use an LLM.

`api_key.txt` is intentionally ignored by git and is not loaded automatically.
Use the `DEEPSEEK_API_KEY` environment variable when you want real API calls.

## Conversational CLI

Start the CLI:

```bash
# Complete system (default)
evolex chat

# Explicit aliases for the complete system
evolex chat --pipeline system
evolex chat --pipeline full
evolex chat --pipeline phase3

# Internal debug compatibility only
evolex chat --pipeline phase2
evolex chat --pipeline phase1
```

### Example — Unified System

```text
Agent> EvoLex conversational CLI is ready. System pipeline: phase3.
Agent> Paste technical document text, or enter a local file path. Type help for commands.
EvoLex> API Gateway retries HTTP 503 responses for 2 seconds before failing over.
Agent> I will process this as a short document and run the harness.
Agent> Node completed: ingest
Agent> Node completed: profile
Agent> Node completed: segment
Agent> Node completed: extract
Agent> Node completed: validate
Agent> Node completed: candidate_store
Agent> Node completed: entity_resolve
Agent> Node completed: relation_extract
Agent> Node completed: schema_gap
Agent> Node completed: schema_proposer
Agent> Node completed: quality_review
Agent> Node completed: critic
Agent> Node completed: policy
Agent> Node completed: publish
Agent> Node completed: registry_finalize
Agent> Completed:
       status: published
       segments: 1
       semantic_atoms: 6
       entities: 3
       relations: 2
       claims: 2
       evidence: 2
       policy: publish
       publish: data/kg/RUN-xxxxxxxxxxxx.sqlite
       output: data/candidates/RUN-xxxxxxxxxxxx.jsonl
```

### Commands

The interactive prompt supports Tab completion for commands and local file
paths.

When `DEEPSEEK_API_KEY` is available, natural-language requests are first routed
through the LLM intent parser, with deterministic local rules as fallback. Both
Chinese and English requests are supported, for example:

```text
EvoLex> 我想查看实体
EvoLex> please show relations
EvoLex> 我想解析 examples/technical_note.txt
EvoLex> can you process examples/technical_note.txt
```

During longer runs, the CLI separates progress logs by stage. With `rich`
installed, these appear in a live progress panel with node status, elapsed time,
recent events, and output paths:

- `[intent]` — command understanding and LLM intent JSON.
- `[llm]` — model request/output summaries from extraction steps.
- `[pipeline]` — graph node completion.

The CLI does not print hidden chain-of-thought; logs expose only user-visible
status and structured model outputs.

| Command | Action |
|---|---|
| `help` | Show available commands |
| `last` | Show the last run result |
| `path` | Show the candidate output path |
| `llm settings` | Show current LLM profile, URL, model, key status, and timeout |
| `set llm url ...` | Update the OpenAI-compatible base URL |
| `set llm model ...` | Update the model name |
| `set llm api-key ...` | Update the API key for this session |
| `set llm timeout ...` | Update the request timeout in seconds |
| `exit` | Exit the CLI |

System inspection commands:

| Command | Action |
|---|---|
| `entities` | List resolved entities from the last run |
| `relations` | List extracted relations from the last run |
| `quality` | Show quality scores from the last run |
| `candidates` | Show recent candidate objects from the registry |
| `quarantine` | Show recent quarantine records and reasons |
| `policy` | Show recent policy decisions |
| `schema` | Show schema proposals accumulated across runs |
| `audit` | Show recent node audit events |
| `system` / `full` / `phase3` | Confirm the unified system mode |

Legacy debug commands such as `phase1` and `phase2` are still recognized, but
the chat interface stays on the unified system pipeline and points you to the
explicit debug override if you really need an internal stage.

You can also enter a local file path:

```text
EvoLex> examples/technical_note.txt
```

## Evaluation And Replay

Run the local frozen corpus regression baseline:

```bash
evolex eval frozen
```

Run shadow evaluation. Shadow mode writes reports and candidate/registry
artifacts under evaluation directories, but the publish node does not write a
production KG:

```bash
evolex eval shadow
```

Normal chat runs write checkpoints after each graph node. You can replay a run
or resume the latest checkpoint for a thread:

```bash
evolex run replay --run-id RUN-xxxxxxxxxxxx
evolex run resume --thread-id document:DOC-xxxxxxxxxxxx:v3
```

Schema proposals can be promoted through automatic gates. A proposal must have
enough cross-run support and must not be blocked by shadow/frozen governance
signals:

```bash
evolex schema candidates
evolex schema promote-ready
evolex schema promote --proposal-id scp-xxxxxxxx
evolex schema promotions
```

## English Prompt And KG Policy

All model prompts are written in English.

KG-facing fields use English-only schema labels and normalized values:

- `type`
- `text`
- `kg_language`

The `evidence` field preserves the original source span for traceability, so it
may contain the source document language.

## Candidate Output

Phase 1 writes candidate records to JSONL files under `data/candidates/` by
default. Each record includes:

- `run_id`
- `document_id`
- `object_type` — `"atom"`, `"claim"`, `"evidence"`, `"mention"`, etc.
- `object`
- `created_at`

Phase 3 also writes to a **Candidate Registry** (SQLite, one per run under
`data/registry/`) for structured querying without reading JSONL files.

## Knowledge Graph Output (Phase 2 & 3)

Phase 2 writes a SQLite knowledge graph under `data/kg/`. Each `.sqlite` file
contains these tables:

| Table | Contents |
|---|---|
| `entities` | Resolved entities with canonical text, type, merge count |
| `entity_segments` | Many-to-many mapping between entities and source segments |
| `entity_decisions` | Per-mention resolver decisions (LINK / CREATE_CANDIDATE / AMBIGUOUS / REJECT) |
| `relations` | Subject–predicate–object triples with evidence and confidence |
| `quality_scores` | Per-atom and per-relation quality scores and issues |
| `runs` | Run metadata (run_id, document_id, status, counts, timestamp, versions) |
| `run_audit` | Node execution order, status transitions, policy decisions |

## Schema Candidate Output (Phase 3)

Phase 3 schema proposals are accumulated in a cross-run SQLite store under
`data/schema_candidates/`. Proposals carry stability signals (occurrence count,
independent document count, relation pattern consistency, evidence coverage)
that can be used for automated promotion. Promotion updates only schema
candidate metadata and the promotion ledger; it does not rewrite the production
KG.

## Data Model (Phase 3)

Phase 3 introduces typed objects with required field validation:

| Object | Key Fields |
|--------|-----------|
| `Claim` | `subject`, `predicate`, `object`, `evidence_ids[]`, `conditions[]`, `measurements[]` |
| `Evidence` | `evidence_id`, `document_id`, `segment_id`, `text`, `span_start`, `span_end` |
| `Condition` | `parameter`, `value`, `unit` |
| `Measurement` | `parameter`, `value`, `unit`, `text`, `evidence` |
| `Mention` | `text`, `normalized_text`, `mention_type`, `evidence` |

Every `Claim` must link to at least one `Evidence` — validation enforces this.

## Resolver Decisions (Phase 3)

The entity resolver produces typed decisions instead of blind merges:

| Decision | Meaning |
|----------|---------|
| `LINK` | Matched an existing canonical entity |
| `CREATE_CANDIDATE` | New entity created from this mention |
| `AMBIGUOUS` | Cannot disambiguate; held for review |
| `REJECT` | Text too short or confidence too low |

## Policy Routing (Phase 3)

The policy node evaluates signals (evidence coverage, critic verdict, risk level)
and routes via conditional edges:

| Action | Description |
|--------|-------------|
| `publish` | Low risk, sufficient evidence → write to KG |
| `candidate` | Medium risk or partial evidence → hold as candidate |
| `quarantine` | High risk or critic rejection → isolate with reason label |
| `reject` | Deterministic violations → discard |

## Tests

Run the local test suite (uses no-network heuristic extractor):

```bash
pytest
```

To run the DeepSeek-powered end-to-end test:

```bash
export DEEPSEEK_API_KEY="your-api-key"
python scripts/e2e_test.py
```

Or with the API key file:

```bash
DEEPSEEK_API_KEY=$(cat api.txt) python scripts/e2e_test.py
```
