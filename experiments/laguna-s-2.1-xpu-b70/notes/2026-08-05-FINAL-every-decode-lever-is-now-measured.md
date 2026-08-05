# Every decode lever is now measured, and 250 tok/s is out of reach

Date: 2026-08-05 America/Toronto

Status: **closure. Both halves of `tok/s = tokens_per_step / step_time` are
bounded by measurement, and the product cannot reach 250 at short context on
this stack. One small quality-neutral win remains unbuilt.**

## The identity

`tok/s = tokens_per_step / step_time`. Reaching 250 from the measured
**162.0** requires improving one or both. Both are now bounded.

## Step time is bounded at 14.71 ms

Three arms, q12, measured this session
([detail](2026-08-05-FINAL-250-tok-s-is-at-the-floor-of-this-implementation.md)):

| component of the 25.82 ms step | cost | status |
| :--- | ---: | :--- |
| removable half of the collectives | 5.61 ms | blocked: replicated attention is +3 GiB/rank short of a B70 |
| MoE expert compute | ~5.50 ms | is the model; bandwidth on INT4 expert weights |
| remainder | **14.71 ms** | ~9 ms still unattributed |

250 tok/s at 3.657 tokens per step needs a **14.60 ms** step. The remainder
alone is 14.71 ms, so the target is unreachable even granting both impossible
removals.

## Tokens per step is bounded at ~4.1 on a chain

The drafter's measured rank-1 acceptance is **0.756**
(`laguna_tree_spec.py`: the target's greedy token is the drafter's first choice
72.2% of the time, 84.2% within its first two). A chain therefore converges to

    1 + p/(1-p) = 1 + 0.756/0.244 = 4.098 tokens per step

and depth 11 already realises 3.956 of it. **No amount of additional depth
helps** -- which is why depth 11 was chosen, and why the depth sweep measured
so little.

## Trees and width, computed and measured

`build_greedy_tree` exists in the fork and **has no callers**. Scoring it
against `build_chain` on the module's own measured rank probabilities:

| verifier width | chain | greedy tree | tree gain |
| ---: | ---: | ---: | ---: |
| **12 (today)** | 3.956 | **4.084** | **+3.3%** |
| 16 | 4.052 | 4.381 | +8.1% |
| 24 | 4.093 | 4.788 | +17.0% |
| 32 | 4.098 | 5.071 | +23.8% |

Width looks attractive until it is priced. The 2026-07-26 measurement of width
16 found **+0.21% emitted per cycle for +14.61% cycle time**, and warned that
"the wider verifier is not free -- a point every earlier projection got wrong by
assuming flat cycle time."

Applying that cost to the *optimal tree* rather than the chain it measured:

    (4.381 / 3.956) / 1.1461 = 0.966

**a 3.4% net loss.** Width 16 also failed exactness 0/13 for two independent
reasons. Width is closed, and wider is worse: the tree gain grows sublinearly
while the row cost does not.

## What remains, and it is small

**The greedy tree at the current width 12 is worth +3.3% for zero extra rows**,
hence zero extra cycle time. That is 162.0 -> about **167 tok/s**,
quality-neutral because verification stays exact, and the topology builder is
already written. It is the only unbuilt lever left that is not blocked by
hardware, the model, or a measured cost.

## The complete ledger

| lever | measured | verdict |
| :--- | ---: | :--- |
| collective rendezvous count | -21.7% | blocked, +3 GiB/rank short |
| MoE expert compute | -21.3% | is the model |
| collective bytes | -4.6% | already 69% of PCIe |
| draft depth | -3.0% | tail already spent by depth 11 |
| graph break count | -2.4% | rejected, breaks 32K exactness |
| attention kernel | ~1.25 ms total | not worth attacking |
| verifier width 16 | +0.21% tokens, +14.6% cycle | closed, and inexact |
| **greedy tree at width 12** | **+3.3% tokens, +0% cycle** | **unbuilt, worth doing** |

## The honest bottom line

**250 tok/s at short context is not achievable on this hardware with this
model.** The reachable figure is about **167** with the tree, or about **202**
if a device with ~3 GiB more per rank unblocked the collective lever
(4.084 / 20.21 ms).

**200 tok/s at 32,640 is further out still**: it is gated at 1.058 tokens per
step by a drafter whose sliding window is 512 against a 32K context, and no
step-time or tree work addresses that. It needs a drafter with full-attention
layers, which does not exist on disk.

Those are weights and hardware conclusions, not engineering ones, and they are
now supported by measurement on every route rather than by argument.

## Boundaries

All figures q12, depth 11, width 12, TP4, EP4, warm, cold prefix cache, against
`20260804-eventprofile-q12` from the same stack. Tree scores are exact
arithmetic on `laguna_tree_spec.py`'s own measured rank probabilities over
2,131 record-configuration cycles, not simulations. The width-16 cost is the
2026-07-26 measurement. No quantisation change, and no caching or speculation
setting used to inflate any number. The protected `125.4619731637751 tok/s`
conventional short-decode record is untouched.
