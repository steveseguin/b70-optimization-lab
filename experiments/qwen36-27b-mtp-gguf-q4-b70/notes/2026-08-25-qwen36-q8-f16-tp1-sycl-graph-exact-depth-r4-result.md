# Qwen3.6 target-Q8/F16 TP1 SYCL-graph exact-depth R4 result

State: **passed seven raw graph cells; quality pending**.

| Active context | Prefill tok/s | Decode tok/s | Prefill graph phase | Decode graph phase |
|---:|---:|---:|---|---|
| 0 | 899.265915 | 19.355301 | capture-and-replay, no cache full | verified capture-and-replay |
| 2K | 881.865090 | 19.176343 | mixed partial, cache-8 full | verified capture-and-replay |
| 4K | 855.858875 | 19.078642 | mixed partial, cache-8 full | verified capture-and-replay |
| 8K | 818.751778 | 18.846417 | mixed partial, cache-8 full | verified capture-and-replay |
| 16K | 753.437667 | 18.409273 | mixed partial, cache-8 full | verified capture-and-replay |
| 24K | 698.232196 | 18.007720 | mixed partial, cache-8 full | verified capture-and-replay |
| 32K | 651.490825 | 17.617525 | mixed partial, cache-8 full | verified capture-and-replay |

All seven exact-depth rows passed the parser and every decode phase replayed
all 641 requested graphs. Depth 0 also fully captured and replayed its prefill
phase. At 2K through 32K, prefill used the preregistered phase-aware
classification: the fixed cache records and replays eight graph shapes while
the remaining distinct prefill shapes are disclosed as `cache_full`. Those
prefill phases are mixed partial graph, not fully graph certified.

Cleanup passed. The terminal receipt, raw files, binary/source/model identity,
graph backend, and checksum-bound 32-DSO closure are preserved in the structured
result. These are seven raw cells only: the required quality gate remains
pending, so site publication, quality claims, and record submission are not yet
authorized. No protected graph-off value was touched or replaced.
