# BF16 per-subgraph activation conversion cache

Date: 2026-08-12

## Decision

Keep as a default-off exact kernel win. Source commit `9e019d206` adds
`GGML_SYCL_BF16_GRAPH_CONVERSION_CACHE=1`.

The TP meta backend separates many projections into distinct per-device
subgraphs, so the earlier adjacent gate/up source fusion is unreachable. Within
each reachable simple-backend subgraph, however, multiple BF16 projections can
consume the same F32 activation (for example Q/K/V). The new cache performs the
F32-to-BF16 conversion once per unique activation pointer for the duration of
one subgraph invocation and reuses that exact BF16 buffer for subsequent oneDNN
GEMMs. It is cleared at every subgraph boundary, preventing stale reuse when
the graph allocator recycles pointers across rounds.

## Strict adjacent A/B

Both arms use the primitive and memory-binding caches, disable the dead pair
flag, keep oneDNN matmul and attention, and differ only in the conversion cache.

| Arm | Prose | Code | JSON | Arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| control | 40.031 | 62.144 | 69.150 | 57.108 |
| conversion cache | 40.465 | 62.624 | 69.881 | 57.657 |
| improvement | +1.08% | +0.77% | +1.06% | **+0.96%** |

All output hashes are exact (`914f754747d0edaa`, `cf2b2c4fd9e36fe5`,
`4f813a9706abc163`) and drafted/accepted counts match exactly at
1150/173, 760/201, and 672/207.

Evidence:

- config: `sweeps/20260812-bf16-graph-conversion-cache-ab.json`;
- result: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/bf16-graph-conversion-cache-ab-20260812.jsonl`;
- result SHA-256: `d9b75ed8580e7181de86c532fd64c7b8ccdeb786a4445fca5efbab8c95460a26`;
- production restore health: `data/muse-health-20260812-conversion-cache-restore.json`.

This is a supporting kernel win, not a standalone route to 100 t/s.
