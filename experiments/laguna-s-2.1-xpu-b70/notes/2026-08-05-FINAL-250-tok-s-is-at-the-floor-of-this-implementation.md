# 250 tok/s short context sits exactly at this implementation's floor

Date: 2026-08-05 America/Toronto

Status: **measured, three arms, one control. The strongest feasibility
statement the campaign has produced about the short-context target, and it is
negative.**

## The decomposition

All at q12, depth 11, width 12, warm, cold prefix cache, step time from mean
inter-token latency:

| arm | gathers | MoE experts | step ms | topology |
| :--- | ---: | :--- | ---: | :--- |
| q12 baseline | 96 | on | **25.82** | 146/145 |
| gather-skip mod 2 | 48 | on | **20.21** | 146/145 |
| skip-experts | 49 | **off** | **14.71** | **99/98** |

Both diagnostic arms are **deliberately inexact** and their throughput is not a
rate Laguna can achieve; only the step time is used.

Subtracting:

| component | cost per step | share |
| :--- | ---: | ---: |
| the removable half of the collectives | **5.61 ms** | 21.7% |
| **MoE expert compute** | **~5.50 ms** | **21.3%** |
| everything else | **14.71 ms** | 57.0% |

The MoE figure is the *marginal* one: the skip-experts arm also retires the 47
MoE final-combine gathers, because that all-gather is issued inside the expert
call, so its 11.11 ms saving is 5.61 ms of collectives plus ~5.5 ms of compute.

## Why this settles the short-context target

250 tok/s at the measured **3.657 tokens per step** requires a **14.60 ms**
step.

**The remainder after removing both is 14.71 ms.** So even in a hypothetical
build with half the collectives gone *and the entire mixture-of-experts
computing nothing*, the step would still be 14.71 ms and the rate 248.6 tok/s
-- and that hypothetical is not buildable, because:

- the collective half requires replicated attention, which
  [does not fit on a B70](2026-08-05-KEY-replicated-attention-does-not-fit-on-a-b70.md)
  by about 3 GiB per rank; and
- the MoE compute is the model. Removing it is not an optimisation.

**250 tok/s at short context is therefore not reachable on this stack**, and
the margin is not close in the sense of "needs more engineering" -- it is exact
to within 0.1 ms of a bound that assumes two impossible things.

## Is the MoE compute itself reducible?

Probably not meaningfully, and not without quality loss. At M=12 with top-10
routing over 256 experts on EP4, each rank reads the INT4 weights of every
distinct local expert any of its 12 rows selected. One expert is
`3 x 3072 x 1024` at INT4, about 4.7 MB; a few tens of distinct experts per
layer across 48 layers is gigabytes per step, and ~5.5 ms against 587 GB/s of
measured bandwidth is close to what simply *reading those weights* costs.

So the MoE term is **bandwidth on expert weights**, and the levers that would
shrink it are exactly the two that are excluded: activating fewer experts
(changes the model's output) or quantising further (explicitly forbidden).

## What this does not say

- It does not bound **32,640**, which is gated by acceptance at 1.058 tokens
  per step, not by step time.
- It does not say the 14.71 ms remainder is irreducible. It contains 49
  gathers, attention (~0.9 ms), the drafter (~2.6 ms), 146 graph replays
  (~2.1 ms), sampling and scheduling. Roughly 9 ms of it is still
  unattributed, and the campaign's method -- differential arms, never
  profilers -- can keep bisecting it.
- It does not say a **higher tokens-per-step** cannot reach 250. At the same
  25.82 ms step, 250 tok/s needs **6.46 tokens per step** against the measured
  3.657. That is an acceptance problem, and it is the only remaining route to
  the target that the evidence does not foreclose.

## The honest recommendation

The short-context target should be **re-scoped or pursued through acceptance**,
not through step time. Every step-time lever has now been measured:

| lever | measured | status |
| :--- | ---: | :--- |
| collective rendezvous count | -21.7% | blocked, needs +3 GiB/rank |
| graph break count | -2.4% | rejected, breaks 32K exactness |
| collective bytes | -4.6% | already at 69% of PCIe |
| draft depth | -3.0% | small, and costs acceptance |
| MoE expert compute | -21.3% | is the model |
| attention kernel | ~1.25 ms total | not worth attacking |

## Boundaries

q12, depth 11, width 12, TP4, EP4, util 0.80, warm server, cold prefix cache,
32,640 case plus sentinel, baseline `20260804-eventprofile-q12` from the same
stack. The two diagnostic arms compute wrong answers on purpose; their
retrieval checks fail and their acceptance is meaningless, which is why only
step time is quoted and why neither is a rate. No quantisation change. The
protected `125.4619731637751 tok/s` conventional short-decode record is
untouched.
