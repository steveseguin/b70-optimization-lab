# The step floor is 14.43 ms, and roughly half the decode step is recoverable

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
