# The XPU event profile inflates the step 3.4x, and non-uniformly

Date: 2026-08-05 America/Toronto

Status: **measured, and the instrument is rejected for this question. Its
per-segment proportions must not be quoted. The sixth tool this session whose
own overhead changed the thing it was measuring.**

## What it produced

`VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_ROOT` on qdepth depth 11, all four ranks,
target capture only (qdepth sets `DFLASH_SEGMENTED_GRAPH=0`, so the drafter has
no competing capture):

| kind | count | sum ms | median us | share |
| :--- | ---: | ---: | ---: | ---: |
| graph | 146 | 84.5 | 588.9 | **65.5%** |
| collective | 97 | 32.3 | 330.4 | 25.0% |
| attention | 48 | 12.3 | 251.4 | 9.5% |
| **total** | 291 | **129.1** | | |

Read naively this says the model's own compute inside graph segments dominates
the step. **That reading is wrong.**

## Why it is wrong

The same run's benchmark reports the 32,640 decode step at **126.70 ms**. The
unprofiled qdepth depth-11 step is **37.33 ms**.

**Profiling inflated the step 3.4x.** The profile is measuring itself
faithfully; what it is measuring is no longer Laguna.

Worse, the inflation is not uniform. Against independently measured device
costs:

| component | profiled median | real | inflation |
| :--- | ---: | ---: | ---: |
| attention, per call | 251.4 us | ~19 us (kineto) | **13x** |
| collective, per call | 330.4 us | ~252 us (kineto) | **1.3x** |
| graph segment | 588.9 us | ~14 us (inline-arm delta) | **~42x** |

An XPU event at every one of 292 boundaries forces ordering on the stream, so
kernels that normally overlap cannot. Components with many small kernels
(graph segments, attention) inflate enormously; a single large collective that
was already serialising inflates barely at all. **The 65.5% graph share is
manufactured by the instrument.**

## What the undistorted numbers still say

Multiplying independently measured per-call device costs by the audited counts:

| component | per call | count | per step |
| :--- | ---: | ---: | ---: |
| collectives | ~252 us | 97 | **~24.4 ms** |
| graph replays | ~14 us | 146 | ~2.0 ms |
| attention | ~19 us | 48 | ~0.9 ms |
| **serialised sum** | | | **~27.3 ms** |

against a real 32K step of ~33-37 ms. That is consistent, and it puts the
collectives at the overwhelming majority of serialised device time -- which is
what the kineto trace said, and what the -21.7% gather-halving result is
consistent with once overlap is allowed for.

## The rule this keeps re-teaching

Before trusting any instrument on this stack, **check that run's own end-to-end
throughput against the unprofiled baseline.** Every tool that has failed this
session failed the same check:

| tool | claimed | actual |
| :--- | :--- | :--- |
| torch profiler, cold | 6x cost | 2.7% warm |
| kineto summed collective time | 94% collective-bound | -4.6% when removed |
| host-call replay telemetry | 8.1 ms of attention boundary overhead | 0.67 ms when retired |
| **XPU event profile** | **graph segments are 65.5%** | **step inflated 3.4x** |

## Disposition

The profile stays, default off, and `TARGET_ONLY` is now implemented so it can
at least attach to the right capture on q12. But it cannot answer "where does
the step go" while it changes the step by 3.4x, and no future note should cite
its proportions.

The remaining honest statement about the floor is in
[`2026-08-05-what-is-in-the-20ms-floor.md`](2026-08-05-what-is-in-the-20ms-floor.md):
the drafter is ~8%, non-collective device kernels are ~2.3 ms, and the majority
is still unattributed. **Differential end-to-end arms remain the only method
that has settled anything in this campaign.**

## Boundaries

qdepth depth 11, width 12, TP4, util 0.80, EP4, warm server, cold prefix cache,
32,640 case. All four ranks wrote profiles and agreed to within 0.5% on total.
No quantisation change, no caching or speculation setting used to inflate any
number. The protected `125.4619731637751 tok/s` conventional short-decode
record is untouched.
