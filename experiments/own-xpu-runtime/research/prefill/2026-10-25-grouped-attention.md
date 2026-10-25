# Grouped prefill attention rows (2026-10-25)

In batched prefill, QSA attention used to replay once per prompt row: three launches (admit, tiles, combine) per row
per QSA layer. `OWNRT_PREFILL_ATTN_ROWS=T` (default 4, at most 4) issues one launch set per T consecutive rows instead:
- the p49 split32 kernel already indexes every binding by row r < tokens;
- each row keeps its own query, ids, slot count and causal bound;
- combine stops at the row's own count, so each row's arithmetic equals its single-row replay.

The per-row bindings are the multi-row prefill shadows, viewed at the group's first row through a temporary
self-view. The engine's score/probability scratch is now sized for 4 rows.

**Harness.** Rank 1 alone on card 47:00.0 through
[engine/tools/tp_rank1_driver.py](../../engine/tools/tp_rank1_driver.py): `--prompt 3000 --batched --rows 32`, then
4 decode steps, with warm JIT caches (`--cache`).

| T | Prefill per row | Exact against T=1 |
|---:|---:|---|
| 1 | 10.54 ms | — |
| 4 | **10.25 ms** (−2.8%) | yes, all 1,079 buffers ([T=1](2026-10-25-pj-base-summary.json), [T=4](2026-10-25-pj-group-summary.json)) |

The gain is small because the replayed per-row launches were already prepared commands: grouping removes launches,
not attention work.

The same harness gives the warm prefill baseline for rank 1, 256 rows at short context:
- token by token: 16.8 ms per row;
- batched: 9.7 ms per row.
