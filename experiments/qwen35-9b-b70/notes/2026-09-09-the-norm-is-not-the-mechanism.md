# The serialised norm is not the mechanism at TP1 either (2026-09-09)

`b1sn`: depth-1 concurrency ladder with `VLLM_XPU_RMSNORM_SERIAL_ROWS=256`, matched 1:1 against
`d1` - same depth, same rungs, same capture, same host, same card, both serial on a quiet card.
The knob is verified present in the container (`"VLLM_XPU_RMSNORM_SERIAL_ROWS=256"` in the ladder
container's recorded environment), so this is a real intervention rather than a silent no-op.

| users | d1 exact (two passes) | b1sn exact (two passes) | d1 tok/s | b1sn tok/s |
| ---: | --- | --- | ---: | ---: |
| 1 | 1/1, 1/1 | 1/1, 1/1 | 95.6 | 95.9 |
| 2 | 2/2, 2/2 | 2/2, 2/2 | 184.8 | 184.9 |
| 4 | 4/4, 4/4 | 4/4, 4/4 | 322.7 | 322.7 |
| 8 | 8/8, 8/8 | 8/8, 8/8 | 554.9 | 555.9 |
| 16 | 16/16, 16/16 | 16/16, 16/16 | 905.0 | 898.5 |
| 32 | 30/32, 31/32 | 31/32, 31/32 | 988.4 | 989.0 |
| 64 | 60/64, 61/64 | 62/64, 60/64 | 1034.5 | 1033.5 |

**Pooled divergence: 10/254 (3.94%) baseline against 8/254 (3.15%) treated.** Two events apart,
with a Poisson standard error of about 3.2 on the baseline count. That is no difference.

## What this closes

The row-count dependence of the RMSNorm is **not** what costs exactness under speculation on this
lane. This was the leading hypothesis and the reason `b1sn` was promoted to the front of the queue.

The two-card campaign reached the same verdict (0.7031% -> 0.5469%, n.s. over 1280 requests per arm)
but that was about the cross-card collective, and the correct reading at the time was that it did
not transfer to TP1. It now has an independent TP1 elimination on a lane with no collective at all
to confuse the attribution. The norm is out on both.

## What it confirms

The knob is **free at TP1**, extending the earlier TP2 cost measurement: 95.9 against 95.6 at one
user and 1033.5 against 1034.5 at 64 users, with every intermediate rung inside a percent. If a use
for it is ever found, it costs nothing to switch on.

## It does not fix the no-speculation divergence either

`b1sn` also ran its own MTP0 ladder with the knob on. At 64 users it measured **1/128 divergent
(0.78%)** against the pooled three-arm baseline of **2/384 (0.52%)** - indistinguishable at these
counts. So the serialised norm changes neither the speculative divergence (3-6%) nor the rare
no-speculation one (~0.5%). It is not the mechanism for anything observed on this lane, which is a
stronger elimination than the speculative arm alone would support.

## Where the search goes next

Remaining candidates, in queue order:

1. `b2rs` - `VLLM_XPU_GDN_ROW_STABLE_RMSNORM`, a different formulation of the same reduction, never
   tested on this model.
2. `b3lm` - `VLLM_XPU_LM_HEAD_BATCH_INVARIANT`. The divergences are exact two-way ties, and the
   lm_head is where a tie is resolved, so this targets the site rather than an upstream perturbation.
3. `c1cap` - the capture confound. At depth 1, 64 users is 128 decode rows against a capture ceiling
   of 64, so the top rungs may run eager. Eager and captured are different execution paths and this
   lane already knows they disagree. If raising the ceiling moves the rate, the mechanism was never
   numerical at all.

`c1cap` deserves promotion above `b2rs`: it is the only candidate that would make the whole
"speculation costs exactness" framing wrong rather than merely incomplete.
