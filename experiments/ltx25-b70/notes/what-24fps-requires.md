# What 24 fps actually requires

*2026-09-16, after the three-stage pipeline (2.563 s interval, 9.8 fps).*

## The accounting

Per clip, on the pipelined arm, with everything that can currently be hidden
already hidden:

| Item | Per clip | Where |
| --- | ---: | --- |
| Sampler (344 + 368) | **2.023 s** | xpu:0 + xpu:1, critical path |
| Latent upsampler (348) | 0.240 s | in-clip |
| Save video (75) | 0.129 s | in-clip |
| Fusion/capture/gates | 0.117 s | in-clip |
| **In-clip total** | **2.509 s** | |
| Text encode | 1.59 s | xpu:2, hidden |
| Decode (video+audio) | ~1.2 s | xpu:3, hidden |

Measured interval 2.563 s. The budget for 24 fps is **1.042 s**.

## Why tuning cannot get there

The sampler alone is 2.023 s. For a 1.042 s interval it would have to reach
about 0.8 s. Its **weight-read floor is 0.74 s**: 48 blocks x 737.5 MB x 11
forwards = 389 GB, at the measured 527.8 GB/s copy roofline. So the sampler
would have to run at 1.08x its absolute floor, meaning essentially all of the
~60% of block time that is not GEMM would have to disappear. It will not.

The other stages are already off the critical path and cannot help further.
Removing the entire text encode and the entire decode from the clock -- which
the pipeline has effectively already done -- still leaves 2.5 s.

## The one path that remains

The sampler is 11 diffusion forwards over 48 blocks, and the blocks are
currently split across **two** cards. Diffusion is sequential *within* a clip:
forward k+1 needs forward k. But it is not sequential *between* clips. Clip
N+1's first forward can occupy the first card-stage while clip N's first forward
is already in the second.

That is ordinary pipeline parallelism, and it changes no arithmetic at all --
each clip still runs the same 48 blocks in the same order with the same inputs.
Only which clips are in flight at once changes.

With the 48 blocks split across four card-stages of 12:

- one stage-visit is 2.023 s / (11 forwards x 4 stages) = **46 ms**
- a clip needs 44 stage-visits, but four stages run at once
- steady-state interval = 44 / 4 x 46 ms = **0.51 s per clip**

That is **2.05 s of video per second of compute, about 49 fps** -- past the goal
with margin, which is what makes it worth the build rather than a last resort.

Memory fits: the transformer is 42 GB over four cards (10.5 GB each), the
encoder 26.2 GB, the VAEs 1.7 GB; 70 GB over four 34.2 GB cards averages
17.5 GB. Several clips' activations in flight is the new cost to budget.

## What makes it hard

ComfyUI executes one prompt at a time in a single worker, so "four clips in
flight through four card-stages" cannot be expressed as four prompts. It needs a
sampler that owns several clips at once and steps them through the stages -- a
real re-architecture of the sampling path, not a gate node.

The cross-device precondition is already measured and holds: two workloads on
two cards from two Python threads hid 100% of the smaller one
([throughput-is-the-goal-metric](throughput-is-the-goal-metric.md)), and the
three-stage pipeline now in place is the same mechanism at clip granularity.

## Honest status

| Milestone | Interval | fps |
| --- | ---: | ---: |
| Session start (serial, latency-measured only) | 4.678 s | 5.3 |
| Three-stage pipeline (landed, bytewise exact) | **2.563 s** | **9.8** |
| Sampler pipelined 4 ways (projected) | ~0.51 s + tail | ~24-40 |
| Goal | 1.042 s | 24 |

Everything through 9.8 fps is measured and bytewise exact. The 4-way figure is a
projection from measured per-stage cost, not a result.

## The 4-stage pipeline, measured

*Added 2026-09-16, [`scripts/stage-pipeline-probe.py`](../scripts/stage-pipeline-probe.py),
exclusive cards.*

Four card-stages, real GEMM work of the measured stage size, eight clips pushed
through with one lock per stage:

| | per clip |
| --- | ---: |
| serial (one clip at a time through four stages) | 1.801 s |
| pipelined (eight clips in flight) | **0.577 s** |
| **speedup** | **3.12x** (ideal 4x) |

The 22% shortfall is GIL and lock overhead, not the hardware. So the mechanism
is real, and the sampler's 2.023 s would become about **0.65 s**.

## But that moves the bottleneck again, and the arithmetic gets tight

Once the sampler is pipelined, the other stages become binding, and all three
compete for the same four cards. The honest figure is total work per clip
divided across four cards:

| Stage | Per clip |
| --- | ---: |
| Sampler | 2.023 s |
| Text encode (fp32, irreducible) | 1.590 s |
| Decode, uncontended | ~0.740 s |
| **Total** | **4.35 s** |

24 fps needs an interval of 1.042 s, so it needs total work per clip of at most
**4 x 1.042 = 4.17 s** at perfect balance and 100% pipeline efficiency. We have
4.35 s, at 78% measured efficiency.

| Scenario | Interval | fps |
| --- | ---: | ---: |
| Today (three-stage pipeline) | 2.563 s | **9.8** |
| All work balanced over 4 cards, ideal | 1.09 s | 22.9 |
| All work balanced over 4 cards, at the measured 78% | 1.39 s | 17.9 |
| Same, with the sampler also at its 0.74 s floor | 0.77-0.98 s | 25-32 |

**24 fps sits just past perfect four-card balance.** It needs the full
re-architecture *and* real reduction in the sampler's own 2.023 s, whose floor is
0.74 s. It is not excluded, but nothing about it is comfortable, and the
build is a rewrite of the sampling path rather than another gate node.
