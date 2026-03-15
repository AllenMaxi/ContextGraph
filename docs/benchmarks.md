# Benchmarks

ContextGraph should feel fast enough to sit directly on the hot path of an agent tool call.

These numbers are a **local baseline**, not a hosted SLA:

- machine: Apple Silicon laptop
- backend: in-memory repository
- runtime: Python 3.13.3
- ranking path: claim extraction + BM25 + freshness/confidence modifiers
- seeded dataset: 300 memories

## Local Baseline

| Path | Avg (ms) | P50 (ms) | P95 (ms) | Max (ms) |
| --- | ---: | ---: | ---: | ---: |
| `store_memory` | 0.02 | 0.02 | 0.03 | 0.07 |
| `recall` | 6.57 | 6.58 | 6.78 | 6.85 |
| `get_feed` | 10.47 | 10.41 | 11.09 | 11.66 |

These are the numbers that matter for agentic systems:

- `store_memory` needs to be cheap enough to persist useful observations during a task
- `recall` needs to fit inside a normal tool-call budget before the LLM answers
- `get_feed` needs to be fast enough for polling dashboards, subscriptions, and proactive agents

## Methodology

Run the benchmark locally:

```bash
python3 scripts/benchmark_local.py
```

The script:

- registers a same-org source agent and two consumer agents
- seeds internal, shared, and paid published memories
- warms the BM25 index
- measures repeated calls to:
  - `store_memory`
  - `recall`
  - `get_feed`

## Design Implication

The intended architecture is:

- use ContextGraph directly as the shared memory bus
- call `recall` at response time for relevant memories
- cache results briefly if needed
- avoid blindly copying third-party memories into another vector database

That keeps:

- access control authoritative
- payment checks intact
- source attribution visible
- stale-memory risk lower
