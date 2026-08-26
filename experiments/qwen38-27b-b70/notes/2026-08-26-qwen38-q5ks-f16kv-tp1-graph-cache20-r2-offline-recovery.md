# Qwen3.8 Q5_K_S/F16-KV TP1 graph cache20 R2 offline recovery

Date: 2026-08-26

## Outcome

The completed R2 raw run is a valid mechanism sentinel under its frozen
cache20 gate. This is a report-only offline recovery, not a GPU rerun and not
a rewrite of the original result. The historical candidate arm remains
`failed-preserve`, its original error remains
`GateError: server graph mechanism evidence failed`, and no historical
terminal receipt or `graph-evidence.json` is manufactured.

The failure was procedural. The R2 runner called the inherited
`GRAPH.IMPL.F16.graph_evidence` helper after generation and cleanup. That
helper hardcodes `cache_limit == 8`, while the R2 preregistration deliberately
requires `cache_limit == 20`. It therefore rejected the valid raw cache20
summary before the runner could write its terminal receipt.

## Recovered evidence

The read-only validator binds all 13 files in the original raw root by exact
path, byte size, and SHA-256. It independently re-parses both server logs and
checks the launch identity, model/runtime identity, graph-only environment
delta, served model, target-only F16-KV argv, exact-depth gates, cache-zero
usage, cleanup, and graph-on/off token/text/usage/prompt parity.

The frozen graph counters are:

- graph off: every counter and `cache_limit` is zero;
- graph on/cache20: `requested=146`, `cache_hit=126`, `cache_miss=20`,
  `cache_full=0`, `direct_replay=126`, `recorded=20`, `created=20`,
  `cache_entries=20`, `cache_limit=20`, `replayed=146`, with rejected,
  unsupported, updated, and recreated all zero.

The control and candidate produced the same 128 output token IDs, text hash,
usage (`8192 + 128`, `cached_tokens=0`), and returned-prompt identity. Their
99-interval serving rates were respectively `23.709149482995137` and
`22.957843669085598 tok/s`; no speed floor was preregistered.

## Authority

This recovery authorizes only a separate reviewed preregistration for the
full Q5_K_S/F16-KV graph context curve. It authorizes zero site cells, no full
curve by itself, no quality-battery, MTP, TP2/TP4, prefill, headline,
protected-value, or LocalMaxxing claim. The protected historical decode values
remain unchanged.

Evidence and validation:

- compact recovery receipt:
  `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2-offline-recovery.json`;
- read-only validator:
  `experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2-offline-recovery.py`;
- preserved raw root:
  `/mnt/fast-ai/bench-results/qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-20260826-r2`.
