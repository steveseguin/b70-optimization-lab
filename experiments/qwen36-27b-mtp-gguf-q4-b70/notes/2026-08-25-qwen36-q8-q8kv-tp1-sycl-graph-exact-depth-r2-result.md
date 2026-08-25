# Qwen3.6 target-Q8/Q8-KV TP1 SYCL-graph exact-depth R2 result

State: **passed seven raw graph cells; quality pending**.

| Active context | Prefill tok/s | Decode tok/s | Prefill graph phase | Decode graph phase |
|---:|---:|---:|---|---|
| 0 | 896.094776 | 19.009751 | capture-and-replay, no cache full | verified capture-and-replay |
| 2K | 871.928100 | 17.932808 | mixed partial, cache-8 full | verified capture-and-replay |
| 4K | 850.230179 | 17.032154 | mixed partial, cache-8 full | verified capture-and-replay |
| 8K | 809.773693 | 15.467807 | mixed partial, cache-8 full | verified capture-and-replay |
| 16K | 747.452109 | 12.709356 | mixed partial, cache-8 full | verified capture-and-replay |
| 24K | 691.398160 | 10.835266 | mixed partial, cache-8 full | verified capture-and-replay |
| 32K | 645.089763 | 9.475195 | mixed partial, cache-8 full | verified capture-and-replay |

All seven exact-depth rows passed the parser and every decode phase replayed
all 641 requested graphs. Depth 0 also fully captured and replayed prefill. At
2K through 32K, cache 8 recorded and replayed eight prefill graph shapes while
the remaining distinct shapes reported `cache_full`; those prefill phases are
therefore mixed partial graph, not fully graph certified.

Cleanup passed. The structured result preserves raw-file hashes, the exact
Q8_0-weight/Q8_0-KV selectors, model and binary identities, graph backend, and
the checksum-bound 32-entry DSO closure. It also records both the final
`metadata.json` file hash and the different metadata hash embedded in the
immutable exact-depth receipt instead of silently equating them.

These are seven raw-engine pp2048/tg128 cells only. The required quality gate
remains pending, so site publication, quality claims, HTTP-serving claims, and
record submission are not authorized. No protected graph-off value was
touched or replaced.
