# Correction: the profiler inflated the collective share

Date: 2026-08-04 America/Toronto

Status: **correction. Supersedes the headline claim in
[`2026-08-04-decode-is-collective-bound-not-bandwidth-bound.md`](2026-08-04-decode-is-collective-bound-not-bandwidth-bound.md)
and the upside table in
[`2026-08-04-collective-latency-floor-and-remaining-upside.md`](2026-08-04-collective-latency-floor-and-remaining-upside.md).**

## What went wrong

The "collectives are 78% of device time" figure came from a torch-profiler
trace. That run's own throughput was never checked against the baseline. It
should have been.

```
profiled run:  128 tokens / 19.467 s = 6.575 tok/s
baseline:                              39.589 tok/s
```

**Profiling slowed decode by 6x.** Torch profiler overhead is charged per kernel
launch, so it inflates count-heavy categories far more than count-light ones. In
this trace, per step:

| kernel | calls/step |
| :--- | ---: |
| `oneccl_allgatherv_pcie` | 98 |
| `gemm_kernel` | 4 |

The single most count-heavy kernel in the model is exactly the one the trace
named as dominant. The attribution and the artefact point the same way, so the
trace cannot separate them.

## What survives

Two classes of number are unaffected.

**Call counts**, which profiling does not change:

- 98 `allgatherv` per decode step
- 14 `allreduce` per decode step
- roughly two collectives per layer across 48 layers

**The standalone benchmark**, which ran with no profiler and no model:

- 45.9 us per allgather at the 72 KiB decode payload
- flat cost from 6 KiB to 72 KiB, so latency-bound
- 6.84 GB/s peak, and oneCCL reports `provider: tcp`
- nine configuration arms change it by at most 3%

## Corrected arithmetic

```
112 collectives/step x 45.9 us = 5.14 ms/step
5.14 ms of a 26.5 ms step      = 19.4%
```

| claim | was | corrected |
| :--- | ---: | ---: |
| collective share of decode | 78% of device time | **~19% of step time** |
| upside from removing all collective time | ~2.0x (~80 tok/s) | **~1.24x (~49 tok/s)** |

Collectives are a real cost and worth fixing, but they are **not** the dominant
term, and no plausible collective work reaches the 150 tok/s target at 32K. The
earlier estimate overstated the prize by more than 30 tok/s.

## What this does not rescue

The bandwidth-roofline framing is still not reinstated. The correction says the
profiled *attribution* was unreliable; it does not restore the assumed
bytes-per-step model that the trace displaced. Where decode time actually goes
is, as of now, **not established** -- roughly 80% of the step is unattributed.

## How to attribute it properly

The profiler cannot answer this: a 6x slowdown redistributes the very quantity
being measured. Two workable routes:

1. **Component benchmarks**, as done for the collective -- isolate attention,
   the MoE GEMM, and the host path in standalone harnesses at decode shapes and
   compare against the 26.5 ms budget.
2. **Differential end-to-end timing** -- change one component and measure
   throughput, never per-kernel attribution under a profiler.

A profiled trace remains useful for *counts* and for *finding* candidates. It
should not be used for time attribution on this stack again without a
throughput check alongside it.

## Boundaries

No measurement changed: 39.589 tok/s at 32K, 152.3 at 1K, 13.31 without
speculation, and the prefill figures all stand. The 6.575 tok/s profiled figure
is an artefact of profiling and is not a regression. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
