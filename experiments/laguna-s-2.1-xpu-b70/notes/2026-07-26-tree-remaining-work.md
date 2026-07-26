# Laguna — the tree: what is built, and exactly what is left

Date: 2026-07-26 America/Toronto

Best measured result: **100.524890** tok/s at width 12, 13/13 bitwise exact,
146/145 topology, against the approved record of 94.920039.

## Why the tree is the only route left

Every other axis is closed by measurement this session: width (12 is the
optimum, 14 and 16 are slower *and* inexact), the exact fusion stack (closed at
all three widths), draft graph capture (rejected, 0/13), and moving the
first-request capture out of the scored window (rejected as a cheat).

## Why it should work

The trade is on measured inputs, not extrapolation. Rank-2 rescue was measured
at width 12 as **43.71%** of position-0 misses, matching the 43.2% seen at width
8.

| shape | emitted/cycle | projected tok/s |
| --- | ---: | ---: |
| spine depth 11 (measured) | 3.9552 | **100.52 measured** |
| spine 10 + alternate at depth 1 | 4.0290 | 102.40 |
| spine 9 + alternates at depths 1, 2 | 4.0556 | 103.08 |

The reason this does not repeat the width-14/16 failure, where acceptance gains
were swallowed by cycle growth: **an alternate replaces a spine node rather than
adding one**. The verifier stays eleven rows wide, so cycle time is unchanged
apart from the private-block copies.

## Built and tested (116 tests, all inert behind no flag)

| module | role |
| --- | --- |
| `laguna_tree_spec.py` | shapes, `build_spine_with_alternates`, `node_token_ids` |
| `laguna_tree_metadata.py` | row layout, private pool, `plan_cycle`, attention tensors |
| `laguna_tree_accept.py` | greedy tree walk, exactness-checked against an oracle |
| `llm_base_proposer.greedy_sample_top_k` | top-k read; column 0 equals greedy |

The invariant that keeps the measured baseline valid: a tree reading only column
0 drafts identically to the chain, and a spine-shaped plan reproduces the chain's
staircase on the rows it shares. Both are pinned by tests.

## Left to do, in order

1. **Env flag** `VLLM_XPU_LAGUNA_TREE_ALTERNATES`, default empty (chain), taking
   the alternate depths. Nothing below activates without it.
2. **Private block pool at cache init.** Reserve `rows * blocks_per_row` blocks
   and keep them out of the request allocator. `LagunaTreePrivateBlocks` already
   validates the pool.
3. **Draft assembly in the proposer.** Read top-2 via `greedy_sample_top_k`, map
   to rows with `node_token_ids`, and emit the tree's tokens in row order.
4. **Slot mapping.** Spine rows keep consecutive slots; alternates write into
   their private blocks at `tail + depth - 1`, per `plan.write_slot`.
5. **Base-tail copy.** One strided copy into each private block before the
   verify forward. All layers alias one `packed_backing` tensor when
   `block_stride > 0`, so this is a single operation rather than 49.
6. **Attention metadata.** Override `xpu_exact_spec_decode` with
   `build_tree_attention_tensors(plan_cycle(...))`.
7. **Acceptance.** `SpecDecodeMetadata` is a flat per-request chain and cannot
   express a tree, so the Laguna tree path must bypass the fused sampler and
   walk host-side with `accept_tree`. Greedy at temperature 0 reduces to argmax
   comparison, and the pipeline already syncs sampled token ids each cycle, so
   this adds no new device synchronisation.
8. **Accepted-alternate KV fixup.** If an alternate is accepted, copy its
   key/value from the private block into the sequence position the next cycle
   will read. One token across all layers, and only on the roughly 12% of cycles
   that accept an alternate.

## Gates that decide it

Unchanged: 13/13 bitwise against the canonical q=1 teacher, `cached_tokens=0`,
146/145 on all four ranks, verified idle either side, and a same-session width-12
control. Two candidates today produced 198.7 and 489.9 tok/s with wrong output;
both showed a nearly flat per-position acceptance row, which is the tell that the
check has stopped working.

## Note for whoever runs the older harnesses

About two dozen tools in `tools/` still hardcode `eno1`. A reboot on 2026-07-26
moved the cluster IP to `eth1`, and oneCCL fails KVS bootstrap with the stale
name. The measurement leg, the ladder, and the top-k probe resolve it at runtime;
the rest do not.
