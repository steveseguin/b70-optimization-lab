# The fixed per-step cost is 145 graph breaks, not bandwidth, bytes or depth

Date: 2026-08-04 America/Toronto

Status: **mechanism identified from the code's own audited topology and from
two prior measured runs. Not yet priced per boundary -- the audited replay
profile does that, and is the immediate next measurement.**

## The topology is fixed and hard-coded

`vllm/compilation/breakable_cudagraph.py` audits the decode replay against an
exact segment topology, and raises `Laguna replay-profile segment topology
drift` on any deviation:

| quantity | value |
| :--- | ---: |
| graph segments | **146** |
| **eager breaks** | **145** |
| of which attention boundaries | 48 |
| of which collective boundaries | 97 |
| total ordered segments | 291 |

The captured artifact is "a list of zero-arg callables". Each break **ends the
cudagraph segment, runs the op eagerly on the capture stream, and starts a
fresh segment**. So one decode step is not one graph replay; it is 291
host-driven segment invocations, 145 of which leave the graph entirely.

Independently confirmed by measurement: the 2026-07-26 attempts recorded
`topology, every rank | 146/145` on all four ranks.

## Why this explains every negative result in the campaign

The break count is **fixed by the model's structure** -- 48 layers, two
collectives each -- and is independent of context length, payload bytes, and
drafter depth. That is precisely the insensitivity profile measured:

| lever tried | change | result | explained by |
| :--- | :--- | ---: | :--- |
| context 256 -> 32,640 | 128x | step 22.4 -> 27.1 ms | break count unchanged |
| remove expert parallelism | -95% collective bytes | **-4.6%** | all-gather became all-reduce: **same 97 boundaries**, fewer bytes |
| drafter depth 11 -> 7 | -36% draft work | **-0.6%** | target topology unchanged |
| collective volume | -20x | no change | boundaries, not bytes |

**The expert-parallelism result is the sharpest confirmation.** It was read at
the time as "collectives are not the cost". The correct reading is that it
removed collective *bytes* while leaving all 97 collective *boundaries* in
place -- and the cost tracked the boundaries.

It also retires the standing puzzle from
[`2026-08-04-explicit-syncs-are-not-the-fixed-cost.md`](2026-08-04-explicit-syncs-are-not-the-fixed-cost.md):
sampling found the process blocking inside `copy_to_gpu` with only ~0.007
explicit `synchronize()` calls per step. Segment boundaries are where the host
waits on the device queue, and there are 145 of them per step by construction.

## The arithmetic

Short context: 22.4 ms step against ~2.2 ms of device kernel time, so ~20 ms
unattributed across 145 breaks -- **~138 us per break**. That is the same order
as the two independent standalone measurements:

- `bench_laguna_step_floor.py`: 145 us per layer with collectives removed
- `bench_laguna_collective_scaling.py`: ~83 us per collective call, linear

Three independent routes landing at 80-145 us per boundary is why this is worth
building on. It is not yet a per-boundary measurement of the real model, which
is the next step.

## The lever, already named by this campaign

The 2026-07-26 matched control tried capturing attention as **nested** graphs.
It measured **+0.53%** and explained exactly why:

> The nested implementation deliberately preserves all outer segments and
> replaces each eager attention call with a tiny separate graph replay. It
> therefore still performs 48 attention-boundary Python calls per target cycle.
> [...] the next candidate should instead record attention directly into its
> surrounding outer segment. That candidate must [...] require exactly
> **98 outer graphs / 97 eager breaks** on every rank: 146/145 minus the 48
> retired attention boundaries.

That candidate was **never built**. `VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS`
exists for the *drafter*; there is no target-side equivalent. The nested
selector `VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS` is pinned to 0 in
`run_laguna_long_context_baseline.sh:432`, which is correct given it buys 0.53%.

Retiring the 48 attention boundaries is a **33% reduction in break count**. At
138 us per break that is ~6.6 ms off a 22.4 ms step, which at today's 3.66
tokens/step is **163.57 -> ~231 tok/s**. The remaining 97 boundaries are
collectives, which is where the sequence-parallel and deferred-reduce ideas
apply -- and the 250 target needs both.

## What is deliberately not claimed

- 138 us per break is **arithmetic on a residual**, not a per-boundary
  measurement. The audited replay profile
  (`VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT` / `_SAMPLES`) records
  `segment_host_call_ns` per segment kind, and will settle it directly. Run
  that before building anything.
- Whether target-side inline attention is *implementable* is unestablished. The
  2026-07-26 note asserts the paged-decode kernel is graph-recordable, which is
  necessary but not sufficient.
- The projection holds tokens-per-step fixed and assumes retired boundaries
  cost zero rather than less.

## Boundaries

No run was performed for this note; it is a reading of the audited topology in
`breakable_cudagraph.py` against prior measured artifacts. No quantisation
change, no caching or speculation setting used to inflate any number. The
protected `125.4619731637751 tok/s` conventional short-decode record is
untouched.
