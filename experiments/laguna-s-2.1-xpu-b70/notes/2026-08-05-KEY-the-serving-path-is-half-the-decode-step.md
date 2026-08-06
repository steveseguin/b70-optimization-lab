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

## Resolved: the device is idle for most of the step

A third attempt succeeded by shrinking the trace -- 4 profile iterations
instead of 25, on the 8,192 case. Two findings.

**First, the "decode-only window" does not exist.** `LAGUNA_PROFILE_DELAY` and
`LAGUNA_PROFILE_ITERS` have **no readers in the vLLM fork**; the harness comment
describes intent that nothing implements. The capture spans 215 s, the whole
benchmark. They are the eighth and ninth referenced-but-unimplemented selectors
found this session.

**Second, the per-event device figures answer the question anyway**, because
they do not depend on the window:

| role | device time | events | mean |
| :--- | ---: | ---: | ---: |
| attention | 5.092 ms | 268 | 19 us |
| gemm | 2.928 ms | 16 | 183 us |
| elementwise | 0.587 ms | 260 | 2 us |
| norm, memory, other | 0.83 ms | 160 | -- |

Non-collective device work totals **~9.4 ms across roughly four decode steps**,
i.e. **~2.3 ms per step** -- matching the independent kineto measurement of the
full configuration exactly. The 215 s "collective" total is the idle
inter-request barrier and must not be counted, the same trap as the original
94%-collective-bound reading.

**Against a 13.4 ms step in this arm, ~2.3 ms of device kernel work means the
device is idle for roughly 83% of the step.** The ~7.5 ms is therefore
**host-side**, which settles the direction the four-arm bisection could not.

What it does **not** settle is *which* host cost: per-op dispatch (fix:
implement `xpu_exact_batched_m1_bmm_out`) or blocking on the queue (fix: async
scheduling). Those need opposite work, and distinguishing them needs a
genuinely decode-scoped sample -- which on this stack means py-spy against a
long generation on a manually started server, since the harness's window
selectors are not implemented.

## The worker idles; the cost is upstream in EngineCore

Sampling the **sentinel decode specifically** -- triggered on the first case's
result line in `bench.stdout`, 8 s at 500 Hz -- gives a completely different
picture from any earlier profile:

| leaf frame during decode | share |
| :--- | ---: |
| `sched_yield` utils.py:48 | **38.0%** |
| `acquire_read` shm_broadcast.py:698 | 11.7% |
| `wait` shm_broadcast.py:196 | 11.7% |
| `memory_fence` shm_broadcast.py:87 | 10.5% |
| `acquire_read` shm_broadcast.py:690 | 5.3% |
| other `shm_broadcast` frames | ~4.2% |
| `_del_library` library.py:477 | 14.6% |

**`sched_yield` plus `shm_broadcast` is ~81% of decode samples.** The worker is
spinning on the shared-memory channel waiting to be handed the next step. It is
not dispatching operators and not blocking on the device queue.

**So I sampled the wrong process.** The worker idles; the ~7.5 ms is upstream in
**EngineCore** -- scheduling, sampling, rejection, input preparation -- while
all four workers wait. That also explains the device being idle ~83% of the
step: nobody has given it work yet.

**This revives async scheduling**, which I ruled out earlier on worker-side
evidence that "the host is busy, not blocked". That reading was about the wrong
host. `--async-scheduling` prepares step N+1 while step N executes, which is
precisely the gap this profile shows.

**Caveat:** only 171 of 653 samples survived teardown filtering, and
`_del_library` at 14.6% shows some teardown still leaked in. The sample is
small. But an 81% concentration in one coherent signature -- spin, acquire,
fence, wait, all on the same IPC channel -- is not the kind of result that
flips on a larger sample.

## Refuted: the engine is not busy either, and the tools are exhausted

Sampling the whole process tree (`py-spy --subprocesses` on `bin/vllm serve`,
4,987 samples, triggered on the decode window) splits by process:

| process | share of kept samples |
| :--- | ---: |
| `VLLM::Worker_TP3_EP3` | 25.9% |
| `VLLM::Worker_TP2_EP2` | 24.4% |
| `VLLM::Worker_TP1_EP1` | 24.0% |
| `VLLM::Worker_TP0_EP0` | 23.5% |
| **`vllm serve` (engine, in-process)** | **1.5%** |

**This refutes the EngineCore hypothesis from the previous section.** If the
engine were spending ~7.5 ms of every step scheduling, sampling and preparing
inputs, it could not be 1.5% of samples. It is idle too.

And the worker entries are bare `process <pid>:"VLLM::Worker_..."` leaves --
py-spy found **no Python stack at all** at those moments. The workers are inside
**native code**. The earlier `sched_yield` / `shm_broadcast` result was only the
Python-visible sliver of their time.

So every layer measures as idle:

| layer | measured | instrument |
| :--- | :--- | :--- |
| device kernels | idle ~83% of the step | decode-scoped kineto |
| engine / scheduler | 1.5% of samples | py-spy, whole tree |
| worker Python | ~81% spinning in IPC | py-spy, worker |
| worker native | **not visible** | -- |

**The ~7.5 ms is in native code that none of the available instruments can
see.** py-spy is Python-only by construction; kineto's collective totals are
polluted by the idle inter-request barrier; and the XPU event profile inflates
the step 3.4x non-uniformly. That exhausts the tools this campaign has.

Attributing it needs a **native** profiler -- `unitrace` or `ze_tracer` at the
Level Zero boundary -- which
[`2026-08-04-explicit-syncs-are-not-the-fixed-cost.md`](2026-08-04-explicit-syncs-are-not-the-fixed-cost.md)
already identified as the next tool when the same question arose about what the
device queue waits on. That recommendation is now unavoidable rather than
optional.

## How to sample EngineCore, for whoever does it next

Two attempts to profile EngineCore failed on process identification, so the
answer is recorded here rather than rediscovered.

**At decode time there are only five processes**, and none of them is a
separate EngineCore:

```
<pid>  .../bin/vllm serve /mnt/fast-ai/llm-models/laguna-s-2.1/int4 --host ...
<pid>  VLLM::Worker_TP0_EP0   <pid>  VLLM::Worker_TP1_EP1
<pid>  VLLM::Worker_TP2_EP2   <pid>  VLLM::Worker_TP3_EP3
```

With `--distributed-executor-backend mp`, **EngineCore runs in-process with the
API server**. A `VLLM::EngineCore` title does appear transiently during
startup, which is what made the first two attempts look like identification
bugs rather than a structural fact.

- **Sample the `vllm serve` process** -- match on `bin/vllm serve`, not on a
  title. That is where scheduling, sampling, rejection and input preparation
  run.
- **Do not** resolve it as the workers' parent: that PID is a spawn helper with
  no Python stack, and py-spy returns **0 samples, 0 errors** against it, which
  looks like success.
- **Do not** rely on `pgrep -f "VLLM::EngineCore"`: it matches only during
  startup, and returns nothing during decode.
- Sampling needs ptrace, so it must run under `sudo`.
- Trigger on the first case's result line appearing in `$run_dir/bench.stdout`
  (`grep -q '"case_id": "laguna-lc-'`), then sample ~8 s at 500 Hz: the
  sentinel's decode begins about a second later and lasts ~1.7 s. Sampling any
  earlier captures model load and graph capture, which is ~98% of the run and
  produced a completely misleading profile once already.
- Filter out any sample whose stack contains `shutdown`,
  `_cleanup_profiling_kv_cache`, `empty_cache`, `make_llir`, `load_model` or
  `_del_library` before computing shares.

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
