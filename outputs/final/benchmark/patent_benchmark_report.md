# EvoLex Joint Extraction Patent Engineering Benchmark

> This is a deterministic project-owned engineering regression, not an external benchmark or a state-of-the-art claim.

Corpus documents: 8; network calls: 0.

| Metric | Legacy separate | Joint + Agent | Delta |
|---|---:|---:|---:|
| Entity F1 | 0.0426 | 1.0000 | +0.9574 |
| Relation F1 | 0.0000 | 1.0000 | +1.0000 |
| Correct relation endpoint-pair recall | 0.0000 | 1.0000 | +1.0000 |
| Endpoint ID validity | 1.0000 | 1.0000 | +0.0000 |
| Relation evidence-contract coverage | 0.0000 | 1.0000 | +1.0000 |
| Joint materialization rate | 0.0000 | 1.0000 | +1.0000 |
| Publish rate | 0.0000 | 1.0000 | +1.0000 |

## Canonicalization and evolution safety

- Declared alias surface identities before canonicalization: 2.
- Canonical identities after cross-document Agent consolidation: 1.
- Duplicate identity reduction on declared alias groups: 0.5000.
- Shadow gate pass rate: 1.0000.
- Deterministic replay pass rate: 1.0000.
- Consensus accept rate: 1.0000.
- Compensating rollback probe passed: True.
- Version history preserved after rollback: True.

## Limitations

- This is a small project-owned regression corpus, not an external benchmark.
- The examples are designed to exercise relation endpoint preservation, predicate extraction, alias consolidation, evidence contracts, and evolution gates.
- Results must not be represented as state-of-the-art performance or generalized to arbitrary domains.
