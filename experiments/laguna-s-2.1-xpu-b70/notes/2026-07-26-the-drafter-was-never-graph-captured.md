# Laguna — the drafter was never graph-captured, and it is 26% of the cycle

Date: 2026-07-26 America/Toronto

Status: **found by re-reading measured Phase 0 data; unmeasured on hardware**
(the host is wedged). Record remains **94.920039** tok/s.

## The finding

`gpu_model_runner.py` wrapped the drafter in a graph wrapper only when the
Laguna M8 breakable graph was **off**:

```python
if (not laguna_m8_breakable_graph and drafter is not None ...):
    drafter.model = BreakableCUDAGraphWrapper(drafter.model, self.vllm_config)
```

The record configuration turns that flag on. So in every record run to date, the
**drafter has executed eager**.

## What it costs, measured

Phase 0 cycle attribution, four ranks, cross-rank spread under 0.2%:

| interval | median ms |
| --- | ---: |
| draft host total | 8.694 |
| `draft_forward` | 9.004 |
| `ctxkv` | 0.480 |
| `pre_ctxkv` | 0.825 |
| `post_draft` | 0.636 |

Against a derived full decode cycle of ~32.8 ms, the draft is **~26%**.

The arithmetic that says this is overhead rather than work: the drafter is
**6 dense layers** (hidden 3072, intermediate 12288, no experts) and takes
9.0 ms, while the target's **49 MoE layers** take roughly 24 ms. Per layer that
is 1.5 ms against 0.49 ms. Sizing the drafter's weights — about 113 M
parameters per layer, sharded over TP4, in BF16 — gives roughly 340 MB to
stream for the whole model, which at plausible bandwidth is under a millisecond.
Nine milliseconds is an order of magnitude off memory-bound, which is the
signature of launch overhead, not computation.

## Why this lever is safer than any verifier work

The drafter cannot affect output correctness. The verifier emits the target's
own greedy continuation whatever the drafter proposes, so a captured draft can
only move the **acceptance rate**, never the tokens. Nothing about the M=8
exactness contract depends on how the draft was executed.

That is a materially different risk profile from the width and tree work, both
of which touch the verifier and must be re-proved exact.

## Sensitivity: what improvement is needed

Cycle 32.8 ms, draft 8.694 ms of it. Holding acceptance fixed:

| draft time reduced by | new cycle ms | throughput | projected tok/s |
| ---: | ---: | ---: | ---: |
| 30% | 30.2 | ×1.086 | 103.1 |
| 50% | 28.4 | ×1.155 | 109.6 |
| 70% | 26.5 | ×1.238 | 117.5 |

**A 30% improvement clears 102.** That is a far more robust margin than the
depth-15 chain, which projects 102.4 and needs everything to go right.

It also *multiplies* with the acceptance levers rather than competing with them:
the tree raises tokens per cycle, this lowers cycle time.

## The change

`VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH`, default off. When set, the drafter gets
its own `BreakableCUDAGraphWrapper` even while the Laguna M8 target path is
active. The two wrappers are independent instances with independent capture
state, so the target's audited 146/145 topology is untouched — which is the
reason the exclusion existed in the first place.

## Caveats

- The 32.8 ms full-cycle figure is **derived**, not measured directly. The
  8.694 ms draft figure is measured.
- Device intervals in the Phase 0 data are stream-ordered and absorb work queued
  ahead of them; they are ordering evidence, not an additive budget.
- Whether the drafter's forward captures cleanly at all is unverified. It
  contains TP4 collectives, which the breakable wrapper handles by eager
  breaks, but the resulting topology has never been observed.
- Every tok/s figure above is a projection.

## Revised priority

1. Width 8 at the record commit — confirm the host recovered.
2. **Draft graph capture** — largest measured cost, exactness-safe, one flag.
3. Width 12 chain — exactness and topology.
4. Width 12 tree — projected 104.7 on acceptance alone.
5. Width 16.
