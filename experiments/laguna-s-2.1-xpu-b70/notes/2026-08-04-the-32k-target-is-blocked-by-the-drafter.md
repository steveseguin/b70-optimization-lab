# The 32K decode target is blocked by the drafter, not the serving stack

Date: 2026-08-04 America/Toronto

Status: **partly superseded 2026-08-06. The drafter's 32K acceptance collapse
remains measured. The deployment conclusion does not: after the M=1 graph fix,
a separate no-drafter configuration measured 63.533 tok/s versus 38.425 for
speculation, diagnostically. Neither reaches 150 or 200 tok/s.**

## The drafter cannot see the context

`dflash-int4/config.json`:

```json
"num_hidden_layers": 6,
"layer_types": ["sliding_attention", "sliding_attention", "sliding_attention",
                "sliding_attention", "sliding_attention", "sliding_attention"],
"sliding_window": 512
```

**All six drafter layers are sliding-window. There is no full-attention layer.**
The target model has 12 full-attention layers out of 48; the drafter has zero.
At any context, the drafter sees only the most recent 512 tokens.

## Acceptance collapses exactly as that predicts

| context | window coverage | draft tokens | accepted | acceptance | tokens/step |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,024 | 50.0% | 374 | 93 | **24.87%** | 3.76 |
| 1,024 | 50.0% | 385 | 92 | 23.90% | 3.66 |
| 1,024 | 50.0% | 396 | 92 | 23.23% | 3.56 |
| 4,096 | 12.5% | 715 | 62 | **8.67%** | 1.97 |
| 4,096 | 12.5% | 660 | 75 | 11.36% | 2.13 |
| 4,096 | 12.5% | 616 | 72 | 11.69% | 2.29 |
| 32,640 | 1.6% | 1254 | 7 | **0.56%** | 1.08 |
| 32,640 | 1.6% | 805 | 8 | 0.99% | 1.08 |

At 32,640 tokens the per-position breakdown is stark:

```
spec_decode_num_accepted_tokens_per_pos_total[0]  = 7
spec_decode_num_accepted_tokens_per_pos_total[1..10] = 0
```

**Beyond the first draft position, acceptance is exactly zero.** The drafter
computes 11 tokens per step and delivers 0.06.

This is not degradation over a run. Sentinel cases at short context, executed
*after* the 32K cases, recover to 19-29%. It tracks context length, and it
tracks it in proportion to how much of the context the 512-token window covers.

## What the targets actually require

Step rate is nearly constant with context: 24.0 ms/step at 1K, 27.3 ms/step at
32K. Throughput differences are almost entirely **tokens per step**, not step
time.

| target | needs | current | verdict |
| :--- | :--- | :--- | :--- |
| >150 tok/s @ 32K | 4.09 tokens/step, i.e. **~29% acceptance at 32K** | 0.56% | **not reachable with this drafter** |
| 250 tok/s @ 1K | 6.0 tokens/step (**45% acceptance**), or 1.64x faster steps, or a mix | 24%, 24.0 ms | needs both a better drafter and kernel work |
| 100 tok/s no-spec | 10 ms/step at M=1 | 75 ms/step | needs **7.5x** faster M=1 steps |

The 32K target requires the drafter to accept at a **higher rate at 32K than it
currently achieves at 1K**. A model whose entire attention span is 512 tokens
cannot do that at 32,640. No serving configuration, kernel optimisation, or
collective fix changes it.

## Consequences for where effort goes

- **Collective work is not the 32K lever.** Even eliminating every collective
  is ~1.24x (~49 tok/s), and the corrected share is ~19% of the step. Worth
  doing, not sufficient, and not first.
- **Kernel work is not the 32K lever either.** Step time barely moves between
  1K and 32K; token yield is what collapses.
- **The 32K lever is a drafter with long-context attention.** Adding
  full-attention layers, or training a drafter that sees past 512 tokens, is the
  only path to the acceptance rate the target implies. That is a model change,
  and outside what tuning can deliver.
- **The no-speculation target is a genuine kernel problem**, and separate: it
  needs 7.5x faster single-row steps, consistent with the measured fact that
  M=1 utilises memory an order of magnitude worse than M=12.

## Why speculation still helps at 32K despite ~0% acceptance

Disabling it measures 0.34x (13.31 against 39.589). At 32K the drafter delivers
almost no accepted tokens, yet speculation is still worth 3x -- because M=12
gives the verifier a batch shape that streams memory efficiently, while M=1 does
not. Speculation is currently buying **batch shape, not tokens**, at long
context. That is worth stating plainly: the mechanism is real, but it is not the
one the design intends.

## The spec, in per-position acceptance

Speculative decoding is sequential: one rejection discards the rest of the
chain, so tokens/step = `1 + sum_{i=1..d} p^i` for per-position acceptance `p`
at depth `d`. Inverting the measured tokens/step gives:

| context | measured `p` |
| ---: | ---: |
| 1,024 | **73.3%** |
| 4,096 | 53.1% |
| 32,640 | **7.4%** |

And what the targets demand:

| target | tokens/step needed | required `p` | current `p` |
| :--- | ---: | ---: | ---: |
| 250 tok/s @ 1K | 6.00 | **86.1%** | 73.3% |
| >150 tok/s @ 32K | 4.09 | **76.6%** | 7.4% |

The 32K target requires `p = 76.6%`, which is **above the 73.3% this drafter
achieves at 1K**. Restated precisely: the drafter would have to be better at
32,640 tokens than it currently is at 1,024. That is the clearest statement of
why the target is out of reach without a different drafter.

## Deeper drafting does not help -- a negative result worth recording

Prior notes list "deeper drafts trade more experts touched against more accepted
tokens" as an open lever with an unswept crossover. It is not open. At the
measured `p = 0.733`, the chain saturates almost immediately:

| depth | tokens/step | tok/s at 24.0 ms/step |
| ---: | ---: | ---: |
| 11 (current) | 3.660 | 152.5 |
| 15 | 3.725 | 155.2 |
| 20 | 3.745 | 156.1 |
| 30 | 3.751 | 156.3 |
| 60 | 3.751 | 156.3 |

Going from depth 11 to unbounded depth is worth **+2.5%**. The chain length is
governed by `p`, not by `d`, and depth 11 already captures 97.6% of what any
depth could deliver. Draft depth should be closed as a lever; the width-12 lock
that constrains it costs almost nothing.

## The alternative to acceptance is step time, and it is steeper

Holding acceptance at today's values, the same targets need:

- **250 @ 1K**: 14.6 ms/step against 24.0 ms today -- **1.64x**
- **150 @ 32K**: 7.2 ms/step against 27.3 ms today -- **3.8x**

Mixtures work too: 150 @ 32K is also reachable at `p = 50%` combined with a 2x
faster step. Any credible plan for the decode targets has to name which of these
two quantities it moves, and by how much.

## Boundaries

All figures are prometheus counters from cold-cache runs already recorded in
this campaign; no new run was needed. No quantisation change, no caching or
speculation setting used to inflate any number. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
