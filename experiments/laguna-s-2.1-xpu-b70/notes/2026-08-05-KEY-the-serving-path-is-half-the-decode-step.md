# The serving path is half the decode step, and it is not closed

Date: 2026-08-05 America/Toronto

Status: **measured, four arms, one control. Corrects the "every lever is
closed" conclusion: the largest single block of the step is serving-path work
that no experiment has yet attacked.**

## The four-arm bisection

q12, depth 11, width 12, warm, cold prefix cache, step time from mean
inter-token latency. Each arm removes one more thing; the two skip arms are
**deliberately inexact** and only their step time is used.

| arm | rendezvous | MoE experts | step ms |
| :--- | ---: | :--- | ---: |
| q12 baseline | 96 | on | **25.82** |
| gather-skip mod 2 | 48 | on | 20.21 |
| skip-experts | 49 | off | 14.71 |
| **skip-experts + mod 2** | ~25 | off | **13.43** |

## The complete decomposition

| component | cost | share |
| :--- | ---: | ---: |
| all 96 collective rendezvous | ~6.9 ms | 27% |
| MoE expert compute | ~5.5 ms | 21% |
| **everything else** | **13.43 ms** | **52%** |

Collectives are ~6.9 ms in total: 5.61 ms for the first 48 and only 1.28 ms for
24 more once MoE is gone. That second figure is **~53 us per rendezvous against
252 us of device time**, which is direct evidence of how much they overlap in
situ -- and it explains the saturation at half without needing any other story.

## What is in the 13.43 ms

From measurements taken earlier this session:

| component | cost | basis |
| :--- | ---: | :--- |
| drafter, all 11 passes | ~2.6 ms | depth sweep in step time |
| 146 graph segment replays | ~2.1 ms | 07-25 telemetry, confirmed at ~14 us by the inline arm |
| target attention | ~0.9 ms | kineto, ~19 us per call |
| static-signature validation | ~0.36 ms | 07-25 telemetry |
| **unattributed** | **~7.5 ms** | -- |

**~7.5 ms -- 29% of the whole step -- is serving-path work that nothing has
measured.** Sampling, rejection, scheduling, input preparation, and whatever
the host waits on between segments.

## Why this reopens the search

The closure note concluded that both halves of
`tok/s = tokens_per_step / step_time` were bounded. That is right about
*tokens per step*, which the drafter's 0.756 rank-1 rate caps at 4.098. It was
too strong about *step time*: the 14.71 ms "remainder" I treated as irreducible
is now 13.43 ms with a further quarter of the collectives removed, and **more
than half of it is neither model nor collective**.

Unlike every other block, this one is not bounded by the model's arithmetic or
by device memory:

- MoE compute is the model, and cannot be reduced without changing outputs.
- Collectives are structural, and the exact way to halve them needs 3 GiB per
  rank this hardware does not have.
- **Serving-path overhead is none of those.** It is host code.

At 3.657 tokens per step, removing 7.5 ms would take the step to 18.3 ms and
the rate from 162.0 to about **200 tok/s** -- comparable to the blocked
collective lever, and with no memory cost.

## The obvious candidate, and its history

`--async-scheduling` exists to overlap host preparation of step N+1 with device
execution of step N, which is exactly the shape of this cost. Two things stand
in the way, and both are recorded:

- The shared-elementwise contract forbids it outright (`async_scheduling` is a
  violation term in the breakable-graph contract).
- The one attempt
  ([`2026-08-04-async-scheduling-inconclusive-device-lost.md`](2026-08-04-async-scheduling-inconclusive-device-lost.md))
  served the 8,192 case correctly at 7.801 and then lost the device with
  `UR_RESULT_ERROR_DEVICE_LOST` at 32K, with no usable control arm.

That attempt was made before this decomposition existed, when the prize looked
speculative. It is now measured at ~7.5 ms, which changes whether it is worth
retrying on a fresh stack with a control arm first.

## The measurement that would settle it, and why it has not run

The harness already supports a **decode-only** profile window:
`LAGUNA_PROFILE_DIR` arms the torch profiler over `/start_profile`, and
`LAGUNA_PROFILE_DELAY` "skips the chunked-prefill iterations so the captured
window is decode steps only". The torch profiler costs **2.7% warm**, so it is
usable here.

Attempting it on the stripped arm failed, and the failure is worth recording
precisely because the obvious diagnosis is wrong:

- the health wait (lines 589-593) **is** before the profiler arm (line 600), so
  the ordering is correct;
- the server logged `Application startup complete` and stayed up for 13
  minutes;
- yet the profiler `POST /start_profile` returned `curl: (7) ... Couldn't
  connect`, and it is that `die` which triggered the SIGTERM.

So the profiling arm **races the server's readiness** rather than being
mis-sequenced, and only when `--profiler-config.torch_profiler_dir` is passed.
A retry loop around the `/start_profile` POST is the repair, and it is now in
the runner (failing fast if the service dies meanwhile).

**The retry fixed the arming and exposed a second, worse problem.** With the
profiler armed, the run **hung in shutdown**: `server.log` stopped changing for
40 minutes at `Waiting for connections to close`, the profile directory stayed
empty, and the runner sat for 54 minutes before being terminated. The trace was
never written. Cleanup was clean -- no vLLM processes survived, host memory
returned to 117 GiB, and `dmesg` showed no GuC resets, so the hang did not
wedge the stack.

**Net: the decode-only window has now failed twice, for two unrelated reasons**
-- a readiness race, then a profiler-export hang. The ~7.5 ms therefore remains
a *quantity without an owner*. Any future attempt should assume the torch
profiler's export path is unreliable on this stack at this trace size and
either shrink `LAGUNA_PROFILE_ITERS` well below 25 or drive a long generation
against a manually started server and sample it with `py-spy` instead.

## What to do next

1. **Attribute the 7.5 ms before optimising it.** Differential arms, not
   profilers -- every profiler this session was wrong by 4-13x. Candidates to
   remove one at a time: the sampler, the rejection sampler, input preparation,
   the scheduler's per-step bookkeeping.
2. **Then retry async scheduling** on a freshly recovered stack, control arm
   first, treating a second `DEVICE_LOST` at 32K as evidence the contract's
   prohibition is load-bearing.

## Boundaries

All four arms q12, depth 11, width 12, TP4, EP4, util 0.80, warm server, cold
prefix cache, 32,640 case plus sentinel, against `20260804-eventprofile-q12`
from the same stack. The skip arms compute wrong answers on purpose: their
retrieval checks fail, their acceptance is meaningless, and their throughput is
not a rate Laguna can achieve. Component costs are arithmetic on measured
differences, not direct measurements of those components. No quantisation
change. The protected `125.4619731637751 tok/s` conventional short-decode
record is untouched.
