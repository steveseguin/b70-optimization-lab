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

## Continued: two further pins, still not capturing

After the collective width pin, running with `PREBUILT_EXACT_ATTN_METADATA=1`
(the record's setting, which avoids the single-row collective path) exposed two
more:

10. `_is_xpu_exact_spec_decode_metadata_eligible` — `1 < max_query_len <= 8`
11. prebuilt metadata buffers sized `8`/`9` and both width enumerations
    `range(2, 9)`

Both parameterized. The run then reached a new failure:

```
XPU exact speculative attention persistent metadata identity drifted
```

so the width-12 metadata is now built and selected, but its persistent identity
or signature check does not accept it. That is pin twelve, not yet diagnosed.

## Honest assessment of scope

Eleven width pins have been found and parameterized so far, each discovered only
by running and reading the next failure, at roughly five to ten minutes per
cycle. The chain has not terminated. This matches the campaign's own prior
statement that depths above seven "require widening or serializing **all** M>8
target verifier boundaries" — the stack is specialized to M=8 in many
independent places, and widening it is a multi-day project rather than a
session's work.

Nothing here is blocked on a decision; it is blocked on the remaining volume of
specialization.

## Next

1. Diagnose pin twelve: the persistent metadata identity/signature check at
   width 12. Adding the failing comparison to the error message is the cheapest
   way to see which of base signatures, offset signature, metadata signature, or
   object identity drifts.
2. Continue the pin chain until the audited graph captures at width 12, then run
   one clean measurement requiring four captures, four-rank replay, 13/13 q=1
   exactness, cache-zero, and a scored median.
3. Then the width-two tree, still required to clear 102 since M=12 alone
   projects only about 101.5 at unchanged cycle time.


## Pin twelve resolved; the collective assumption is the real wall

Pin twelve was another literal in the identity check itself:
`persistent_block_table.shape != (8, block_table.shape[1])`. Parameterized.

The run then returns to the collective failure, and the stack now identifies its
source precisely:

```
laguna.py:1181  o_proj
linear.py:1919  forward
linear.py:102   _xpu_rank_order_all_reduce   ->  all_gather (1, 1, 3072)
```

`_xpu_rank_order_all_reduce` gathers each rank's local `o_proj` result and sums
in fixed rank order — the mechanism that makes q=1 and speculative verification
share reduction arithmetic. Inside the eligible width-12 forward, one such
`o_proj` carries **one row**, not twelve.

The collective state is correctly scoped: `active_laguna_m8_collective_state`
returns non-None only when the forward context is marked eligible. So this is
not leakage across forwards. A genuinely single-row `o_proj` occurs *within* the
twelve-row verifier forward — almost certainly a DFlash layer, since DFlash
decoder layers execute inside the same forward and its context-KV precompute
operates on a different row count than the verifier query.

**This is the structural wall.** `LagunaM8CollectiveState` preallocates
non-aliasing buffers at a single `_ROWS` width and asserts every collective in
the transaction matches it. That assumption is not merely a constant: at M=8 the
verifier width and the DFlash layer width evidently coincide, and at M=12 they
do not. Fixing it requires the transaction to carry per-slot widths, or to
exclude DFlash-layer collectives from the M8 transaction entirely.

That is a design change to the collective manager, and it is where this work
stops for now.
