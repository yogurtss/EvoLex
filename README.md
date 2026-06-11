# EvoLex

EvoLex is a conversational CLI and controlled document-processing harness for
technical document knowledge extraction.

Phase 1 runs a minimal extract-validate-store pipeline. Phase 2 extends it with
entity resolution, relation extraction, quality review, and structured
publishing to a SQLite knowledge graph.

## Pipeline

Phase 1 topology:

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

Phase 2 appends four additional nodes:

```text
  ... -> candidate_store
  -> entity_resolve
  -> relation_extract
  -> quality_review
  -> publish
  -> END
```

- **entity_resolve** — deduplicates entities across segments and assigns
  canonical names (heuristic, no LLM).
- **relation_extract** — extracts relationships between atoms using the LLM
  when available, falling back to proximity-based heuristics.
- **quality_review** — scores and filters atoms and relations; flags
  low-confidence, trivial, duplicate, and dangling-reference items.
- **publish** — writes structured output to a SQLite knowledge graph under
  `data/kg/`.

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

Install `rich` for styled terminal output, progress spinners, and live
intermediate results:

```bash
pip install ".[rich]"
```

Without `rich`, the CLI falls back to plain-text output and no animations.

## DeepSeek API

The extractor uses the DeepSeek OpenAI-compatible chat API when
`DEEPSEEK_API_KEY` is available:

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

Runtime settings:

- `base_url`: `https://api.deepseek.com`
- `model`: `deepseek-v4-flash`

The API path uses the official OpenAI SDK style:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
```

EvoLex passes `reasoning_effort="high"` and
`extra_body={"thinking": {"type": "enabled"}}` for real DeepSeek extraction.

Do not commit API keys. The repository intentionally reads the key only from the
environment.

If `DEEPSEEK_API_KEY` is not set, the harness uses a deterministic local
heuristic extractor so tests and demos can run without network access.

For a forced no-network local run, set:

```bash
export EVOLEX_OFFLINE=1
```

`api_key.txt` is intentionally ignored by git and is not loaded automatically.
Use the `DEEPSEEK_API_KEY` environment variable when you want real API calls.

## Conversational CLI

Start the CLI:

```bash
# Phase 1 only (default)
evolex chat

# Phase 1 + 2 full pipeline
evolex chat --pipeline phase1+2

# Equivalent full-pipeline aliases
evolex chat --pipeline phase2
evolex chat --pipeline full
```

### Example — Phase 1

```text
Agent> EvoLex conversational CLI is ready. Pipeline: phase1.
Agent> Paste technical document text, or enter a local file path. Type help for commands.
EvoLex> API Gateway retries HTTP 503 responses for 2 seconds before failing over.
Agent> I will process this as a short document and run the harness.
Agent> Node completed: ingest
Agent> Node completed: profile
Agent> Node completed: segment
Agent> Node completed: extract
Agent> Node completed: validate
Agent> Node completed: candidate_store
Agent> Completed:
       status: candidate
       segments: 1
       semantic_atoms: 4
       output: data/candidates/RUN-xxxxxxxxxxxx.jsonl
```

### Example — Phase 2

```text
EvoLex> API Gateway retries HTTP 503 responses for 2 seconds before failing over.

  ✓ ingest       ✓ profile      ✓ segment      ✓ extract      ✓ validate
  ✓ candidate_store  ✓ entity_resolve  ✓ relation_extract
  ✓ quality_review   ✓ publish

                    Run Result: RUN-xxxxxxxxxxxx
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field             ┃ Value                                   ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Status            │ published                               │
│ Segments          │ 1                                       │
│ Semantic Atoms    │ 4                                       │
│ Entities          │ 4                                       │
│ Relations         │ 3                                       │
│ Publish Output    │ data/kg/RUN-xxxxxxxxxxxx.sqlite         │
│ Candidate Output  │ data/candidates/RUN-xxxxxxxxxxxx.jsonl  │
└───────────────────┴─────────────────────────────────────────┘
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

During longer runs, the CLI separates progress logs by stage:

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
| `exit` | Exit the CLI |

Phase 2 additional commands:

| Command | Action |
|---|---|
| `entities` | List resolved entities from the last run |
| `relations` | List extracted relations from the last run |
| `quality` | Show quality scores from the last run |
| `phase1` / `p1` | Switch to Phase 1 pipeline |
| `phase2` / `p2` / `full` | Switch to the full Phase 1 + 2 pipeline |

You can also enter a local file path:

```text
EvoLex> examples/technical_note.txt
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
- `segment_id`
- `atom`
- `created_at`

## Knowledge Graph Output (Phase 2)

Phase 2 writes a SQLite knowledge graph under `data/kg/`. Each `.sqlite` file
contains five tables:

| Table | Contents |
|---|---|
| `entities` | Resolved entities with canonical text, type, merge count |
| `entity_segments` | Many-to-many mapping between entities and source segments |
| `relations` | Subject–predicate–object triples with evidence and confidence |
| `quality_scores` | Per-atom and per-relation quality scores and issues |
| `runs` | Run metadata (run_id, document_id, status, counts, timestamp) |

## Tests

Run the local test suite:

```bash
pytest
```

The tests use the no-network heuristic extractor by default.
