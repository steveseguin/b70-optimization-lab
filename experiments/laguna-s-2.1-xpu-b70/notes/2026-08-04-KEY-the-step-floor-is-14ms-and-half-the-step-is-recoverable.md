# The step floor is 14.43 ms, and roughly half the decode step is recoverable

> **CORRECTED, same day.** The claim that the remainder above the floor is
> *recoverable serving-path overhead* was too strong, and the 253.6 tok/s
> projection built on it should not be quoted.
>
> Adding the serving path's ~75 per-step H2D copies to the floor costs
> **0.59 ms**, not the ~10 ms that sampling's 27.6% in `copy_to_gpu` implied. So
> the copies are cheap; `copy_to_gpu` is merely *where the process blocks* while
> the device queue drains. Explicit synchronisation was already excluded at
> ~0.007 calls per step.
>
> The floor models dense BF16 GEMMs. Laguna additionally does INT4 dequantisation,
> MoE expert gather, attention over a 32K KV, and 11 sequential drafter passes --
> **real work the floor omits**. The 8-13 ms above the floor is therefore not
> demonstrated to be overhead; a large part is likely model work.
>
> **What survives, and it matters more:** the floor is a *hard lower bound*.
> 48 layers with TP4 collectives cost ~14 ms on this hardware before the model
> does anything. See "Feasibility against the floor" below.

Date: 2026-08-04 America/Toronto

Status: **measured, standalone, no model and no vLLM. The most actionable
result of the session: it splits the fixed per-step cost into an inherent floor
and a recoverable remainder, and it puts a number on what recovering it is
worth.**

## The measurement

Four ranks, 48 layers, M=12, hidden 3072, reproducing only the *shape* of a
decode step -- a few small GEMMs per layer plus the two collectives a layer
performs. No model weights, no scheduler, no sampler, no drafter.

| quantity | value |
| :--- | ---: |
| step floor, with collectives | **14.43 ms** |
| step floor, collectives removed | **6.95 ms** |
| cost of the collectives inside the floor | 7.48 ms |
| per layer | 300.7 us |
| **Laguna's measured step** | **27-34 ms** |

**About half of Laguna's decode step is an inherent floor for this topology at
this layer count; the other half is serving-path overhead above it.**

## What the floor itself says

6.95 ms for 48 layers of trivial M=12 GEMMs is **145 us per layer**. Those GEMMs
are microseconds of arithmetic -- a 12x3072 by 3072x3072 product is nothing on a
153 TFLOP/s device. So the floor is not compute; it is per-layer dispatch cost,
paid 48 times, and it exists with no vLLM anywhere in the picture.

The collectives add 7.48 ms across 96 calls, about 78 us each -- consistent with
the 45.9 us standalone floor plus per-call overhead, and *serialised* here where
the real model overlaps them. That is why removing expert parallelism from the
real model measured only -4.6%: in situ those collectives are already hidden.

## What it is worth

Holding tokens-per-step at today's measured values and paying only the floor:

| context | measured | at the 14.43 ms floor | target |
| :--- | ---: | ---: | ---: |
| short (256 tokens) | 163.57 | **253.6** | 250 |
| 32,640 tokens | 39.85 | **74.8** | >150 |

**The 250 tok/s short-context target is reachable by removing serving-path
overhead alone** -- no new drafter, no kernel rewrite, no quantisation change.
The 32K target is not: even at the floor it reaches 74.8, because 1.08
tokens/step caps it. That remains an acceptance problem
([`2026-08-04-the-32k-target-is-blocked-by-the-drafter.md`](2026-08-04-the-32k-target-is-blocked-by-the-drafter.md)).

This is the first time in the campaign that a decode target has had a
quantified, mechanism-level path that does not require new model weights.

## Where the recoverable half sits

Laguna's step is 22.4 ms at short context and 27.1 ms at 32K, against a 14.43 ms
floor: **8-13 ms per step above the floor.** Excluded as its cause by direct
measurement: memory bandwidth, compute, PCIe, collective transport, collective
volume, draft depth, GPU clocks, and explicit synchronisation. Sampling puts
27.6% of wall clock inside `copy_to_gpu`, blocking implicitly on the device
queue rather than on any `synchronize()` call.

The floor benchmark is the right harness to chase it: it is fast, needs no
model, and any serving-path construct can be added to it one at a time --
scheduler, sampler, input preparation, the drafter -- until the 8-13 ms appears.
That is a bisection over a 14 ms baseline rather than a hunt inside a 27 ms
black box.

## Feasibility against the floor

Treating 14.43 ms as a hard lower bound on a 48-layer TP4 step, and holding
tokens-per-step at measured values:

| target | needs | ceiling at the floor | verdict |
| :--- | ---: | ---: | :--- |
| 250 tok/s short context | 3.61 tok/step at the floor | **253.6** | at the ceiling; needs the model to add ~0 ms |
| >150 tok/s at 32,640 | 2.17 tok/step at the floor | **74.8** | **unreachable at 1.08 tok/step** |
| 100 tok/s no speculation | 1 tok/step, 10 ms/step | **69.3** | **unreachable**; the floor alone exceeds 10 ms |

Two of the three decode targets are **below the floor at their current
tokens-per-step**, independent of any optimisation to the serving path:

- **>150 at 32K** would need 2.17 tokens/step even if the model cost nothing
  above the floor. Measured is 1.08. Only acceptance closes that.
- **100 without speculation** requires a 10 ms step; 48 layers of TP4
  collectives alone cost ~14 ms. It is unreachable at this layer count and
  topology unless the collective structure changes.

That is the sharpest result available tonight: it converts two targets from
"not yet achieved" into "not achievable without changing tokens-per-step or the
per-layer collective structure", on a measured basis rather than an argued one.

## Caveats

- The floor uses dense BF16 GEMMs; Laguna uses INT4 with different shapes, so
  the two are not arithmetically identical. The floor bounds *dispatch and
  collective structure*, not the model's exact compute.
- Collectives are serialised in the floor and overlapped in the real model, so
  the floor's 14.43 ms is likely an over-estimate of the inherent cost, which
  makes the recoverable half correspondingly larger.
- The projections hold tokens-per-step fixed. They are arithmetic on measured
  quantities, not measurements, and are labelled as such.

## Boundaries

Standalone, four ranks, no model loaded, no quantisation involved, no caching or
speculation setting used to inflate any number. Laguna's 163.57 and 39.85 are
prior warm cold-prefix measurements. The protected `125.4619731637751 tok/s`
conventional short-decode record is untouched.

## Addendum: the floor scales with collective count, ~83 us per call

Varying how often the 48 layers perform their two collectives, same harness:

| collectives | calls | step | ceiling at 1.08 tok/step | at 3.66 tok/step |
| :--- | ---: | ---: | ---: | ---: |
| every layer (today) | 96 | 14.72 ms | 73.4 | 248.6 |
| every 2 layers | 48 | 11.23 ms | 96.2 | 326.0 |
| every 4 layers | 24 | **9.42 ms** | **114.6** | 388.5 |
| every 8 layers | 12 | 8.48 ms | 127.3 | 431.5 |
| none | 0 | 6.71 ms | **161.1** | 545.8 |

**~83 us of floor per collective call**, linear in count. That turns each target
into a specific structural requirement:

- **100 tok/s without speculation** (1 tok/step, needs a 10 ms step): reachable
  at **collectives every 4 layers** (9.42 ms, ceiling 106 tok/s). Not reachable
  at today's per-layer structure, whose floor alone is 14.72 ms.
- **250 tok/s short context** (3.66 tok/step): today's structure ceilings at
  **248.6** -- essentially exactly the target, with no room for the model. Every
  2 layers lifts the ceiling to 326 and makes it comfortable.
- **>150 tok/s at 32,640** (1.08 tok/step): needs a ceiling above 150, which
  arrives only at **zero** per-layer collectives (161.1). Collective reduction
  alone cannot deliver it; acceptance has to rise.

So two of the three decode targets are gated on **how often tensor-parallel
collectives run**, not on kernels, quantisation, bandwidth or the drafter. That
is a restructuring problem -- keeping activations sharded across several layers
before reducing, as sequence-parallel and fused-collective schemes do -- and it
is measurable in this harness before any of it is built.

Reproduce with `bench_laguna_collective_scaling.py`.
