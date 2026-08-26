# Qwen3.8 Q4_K_M/F16-KV TP1 graph cache20 R1 offline recovery

Date: 2026-08-26

## Outcome

The completed R1 raw run passes its frozen cache20 mechanism gate. This is a
report-only offline recovery, not a GPU rerun and not a rewrite of the original
result. The historical candidate arm remains `failed-preserve`, its error
remains `GateError: server graph mechanism evidence failed`, and no historical
terminal receipt or `graph-evidence.json` is manufactured.

The failure was procedural. The Q4_K_M runner delegates execution to the Q5
base runner, which calls the inherited `GRAPH.IMPL.F16.graph_evidence` helper
after generation and clean shutdown. That helper hardcodes
`cache_limit == 8`, while this preregistration deliberately requires
`cache_limit == 20`. It rejected the valid raw cache20 summary before the
runner could write a terminal receipt.

## Recovered evidence

The read-only validator binds all 13 original raw files by path, byte size, and
SHA-256. It independently checks the clean pushed-main launch identity,
Q4_K_M model and graph-runtime identity, graph-only arm delta, served model,
target-only F16-KV argv, both exact-depth gates, cache-zero usage, exact
graph-on/off token/text/usage/prompt parity, and clean shutdown.

The graph counters are:

- graph off: every counter and `cache_limit` is zero;
- graph on/cache20: `requested=146`, `cache_hit=126`,
  `cache_miss=20`, `cache_full=0`, `direct_replay=126`,
  `recorded=20`, `created=20`, `cache_entries=20`,
  `cache_limit=20`, and `replayed=146`; rejected, unsupported, updated,
  and recreated are all zero.

Both arms returned the same 128 output token IDs, text hash, usage
(`8192 + 128`, `cached_tokens=0`), and prompt identity. The graph-off arm
measured `26.39588391738354 tok/s`; graph-on/cache20 measured
`25.481231872416824 tok/s`, or `-3.465131335739635%` in this one sentinel.
That is a recorded adverse direction, not a speed conclusion or speed claim;
the packet preregistered no speed floor.

## Authority

This recovery authorizes only a separately reviewed preregistration for a full
Q4_K_M/F16-KV graph context curve. It authorizes zero site cells and no full
curve, quality-battery, MTP, TP2/TP4, prefill, headline, protected-value, or
LocalMaxxing claim. The protected historical decode values remain unchanged.

Evidence and validation:

- compact receipt:
  `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4km-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r1-offline-recovery.json`;
- read-only validator:
  `experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-q4km-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r1-offline-recovery.py`;
- preserved raw root:
  `/mnt/fast-ai/bench-results/qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-20260826-r1`.
