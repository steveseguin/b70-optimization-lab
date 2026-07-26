# Laguna M=12 — graph eligibility reached, blocked at the collective transaction

Date: 2026-07-26 America/Toronto

Status: **not promoted, goal not met.** Approved record remains **94.920039**
tok/s. No M=12 graph measurement exists.

## Established

- M=12 (DFlash depth 11) is bitwise exact against the canonical q=1 teacher on
  the full 512-token 13-prompt real cold suite, `cached_tokens=0` throughout.
- Speculation genuinely runs at depth 11, verified from server counters:
  1606 drafts, 17666 draft tokens at exactly 11.0 per draft, 4750 accepted,
  against 1718 / 12026 / 4644 for the M=8 record. Emitted per cycle
  **3.958 vs 3.703, +6.9%**.
- Graph eligibility now reaches the capture filter at width 12:
  `mode=PIECEWISE num_tokens=12 verifier=True eligible=True want=12`.

## Width pins found and parameterized behind `VLLM_XPU_LAGUNA_EXACT_MAX_M`

Default 8 at every site, so the record path is unchanged.

1. `_xpu_batched_m1_linear` row cap
2. Laguna `batched_exact_rows` MoE gate
3. `flash_attn` exact speculative attention query cap — **the exactness blocker**
4. Laguna graph contract capture sizes
5. `_validate_laguna_m8_breakable_graph_config` spec depth and capture sizes
6. `_laguna_m8_breakable_graph_capture_filter` num_tokens
7. `_laguna_m8_eligible` unpadded and scheduled token counts
8. `_laguna_m8_eligible` `num_scheduled_tokens.get(req_id)` — **missed initially,
   found by external review; it was the real graph blocker**
9. `laguna_m8_collectives._ROWS`

## Current blocker

The Laguna M8 collective transaction assumes **one fixed row count for every
collective in the transaction**. With `_ROWS` widened to 12 the gather contract
rejects a legitimately single-row collective:

```
Laguna M8 collective input drifted from fixed [1,12,3072] BF16 contract:
got (1, 1, 3072) torch.bfloat16
```

This is structural, not a constant. The transaction pins pre-allocated
non-aliasing buffers per collective slot at a single width; a wider verifier
mixes widths within one transaction. Making it heterogeneous is real design
work on the collective manager, not another parameterization.

## Arithmetic, corrected

+6.9% emitted per cycle applied to the approved **94.920** record projects
roughly **101.5** tok/s **at unchanged cycle time** — and M=12 cycle time will
not be unchanged, since the verifier does more work per cycle. Graphing M=12 is
therefore **necessary but not sufficient** for 102. The width-two tree, whose
+12.0 point top-2 coverage is already measured, remains required on top.

## Measurement integrity

Earlier M=12 runs wrote `identity.txt` files that misdescribed themselves: they
recorded the frozen record commits rather than actual HEADs, and declared
M8/DFlash7 with `metadata_selector=1` while running M=12/depth-11/metadata-0.
Those files are false and none of those runs can support promotion. The harness
now records actual worktree HEADs, `exact_max_m`, `num_speculative_tokens`, the
metadata selector as passed, and the real fusion states, under a schema that
identifies itself as a measurement leg. The exactness and acceptance evidence
above is unaffected because it rests on token ids and server counters.

## Next

1. Make the collective transaction accept heterogeneous per-slot widths, or
   scope the M8 collective manager to the verifier collectives only so that
   single-row collectives bypass it.
2. Then one clean M=12 graph run requiring four captures, four-rank replay,
   13/13 q=1 exactness, cache-zero, and a scored median before any claim.
3. Then the width-two tree, which is still required to clear 102.
