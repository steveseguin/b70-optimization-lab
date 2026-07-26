# Laguna — the projection model, validated out of sample

Date: 2026-07-26 America/Toronto

Status: **model validation on existing measured data.** No new hardware run.
Record stands at **94.920039** tok/s, **3.7031** emitted per cycle, **39.01 ms**
per cycle. This note supersedes the ladders in earlier notes, which mixed model
and measured values in their denominators.

## The record's acceptance curve, measured

From the record run's own Prometheus counters, 1,718 drafts:

| depth | reached | P(reach) | conditional |
| ---: | ---: | ---: | ---: |
| 1 | 1272 | 0.7404 | 0.7404 |
| 2 | 936 | 0.5448 | 0.7358 |
| 3 | 710 | 0.4133 | 0.7585 |
| 4 | 566 | 0.3295 | 0.7972 |
| 5 | 468 | 0.2724 | 0.8269 |
| 6 | 391 | 0.2276 | 0.8355 |
| 7 | 301 | 0.1752 | 0.7698 |

Accepted per cycle 2.7031, emitted 3.7031. Conditional acceptance does not decay
with depth — it drifts *upward*, which is survivor bias: the cycles that reach
depth 6 are the easy ones. That is why the raw conditional curve must not be
extrapolated directly.

## Out-of-sample validation

Fitting a single flat acceptance p to **depth 7 alone** gives p = 0.7600. Its
prediction for depth 11 can then be checked against a measurement it never saw:

| | emitted/cycle |
| --- | ---: |
| flat-p model prediction, depth 11 | 4.0123 |
| independently measured, M=12 run | 3.958 |
| **error** | **1.37%** |

A model fitted on one depth predicting another within 1.4% is the reason the
projections below are worth acting on. Note the naive extrapolation of the raw
conditional curve gives ~4.12 at depth 11 and overshoots, exactly as the
survivor-bias reading predicts.

## The ladder, one consistent basis

All ratios are computed within the model and applied to the measured record.
p₁ = 0.760; p₂ = 0.1263 from the measured top-1 → top-2 increment
(72.2% → 84.2%) scaled by the same factor.

| shape | emitted/cycle | ratio | projected tok/s |
| --- | ---: | ---: | ---: |
| chain 7 — **record, measured** | **3.703** | 1.000 | **94.9 measured** |
| chain 11 — measured | 3.958 | 1.069 | 101.5 |
| chain 15 | 4.115 | 1.111 | 105.5 |
| tree, 11 nodes | 4.133 | 1.116 | 105.9 |
| tree, 15 nodes | 4.436 | 1.198 | 113.7 |

## The second axis

The drafter is 8.694 ms of the 39.01 ms cycle — **22.3%** — and runs eager.
This axis is independent of acceptance and multiplies with it:

| draft time cut | cycle | alone | with an 11-node tree |
| ---: | ---: | ---: | ---: |
| 30% | 36.40 ms | 101.7 | 113.5 |
| 40% | 35.53 ms | 104.2 | 116.3 |
| 50% | 34.66 ms | 106.8 | 119.2 |
| 70% | 32.92 ms | 112.5 | 125.5 |

Alone, draft capture needs about **35%** to clear 102.

## Reading

Three independent routes now clear 102: a depth-15 chain (105.5), an 11-node
tree (105.9), and draft capture at ~40% (104.2). Any two combined carry
substantial margin. The cheapest to try is draft capture — one environment
flag, and it cannot affect correctness because the verifier emits the target's
greedy continuation whatever the drafter proposes.

Everything except the two rows marked measured is a projection from a model
whose only out-of-sample test came in at 1.37%.
