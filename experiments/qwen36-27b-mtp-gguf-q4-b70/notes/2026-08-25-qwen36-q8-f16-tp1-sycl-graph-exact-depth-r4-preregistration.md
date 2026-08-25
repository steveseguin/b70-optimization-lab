# Qwen3.6 target-Q8/F16 TP1 SYCL-graph exact-depth R4 preregistration

R4 is a create-only phase-aware retry of the sealed R3 seven-context packet.
It preserves R3's cache-8 environment, verbose argv, model, source, build,
binary, 32-DSO closure, selectors, contexts, lifecycle safety, and authority.
There is no runtime identity delta.

Each isolated llama-bench process must emit exactly two summaries in the
llama-bench contract order: prefill first, decode second. Both must report
device 0, cache limit 8, and zero rejected, unsupported, updated, and recreated
counts.

Prefill may have `cache_full > 0`. It must satisfy:

- `requested = cache_hit + cache_miss`
- `cache_hit = direct_replay`
- `recorded = created`
- `replayed = cache_hit + created`
- `cache_full = cache_miss - created`
- `requested = replayed + cache_full`

Prefill requests, records, creations, and replays must be positive. When
`cache_full > 0`, graph-on prefill is explicitly **mixed/partial** and is not
fully graph certified; the raw prefill summary and this classification are
retained in `graph-evidence.json` and metadata.

Decode is not weakened: `cache_full=0`, `requested=hit+miss`, `hit=direct`,
`miss=recorded=created`, and `replayed=requested`, with all request, record,
create, hit, direct-replay, and replay counts positive. The evidence output
retains both raw phase summaries plus aggregate counters.

Passing R4 still yields raw cells with quality pending. It authorizes no site
publication, record/submission, quality claim, estimate, or replacement of
protected graph-off measurements.
