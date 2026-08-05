# The fixed per-step cost is 145 graph breaks, not bandwidth, bytes or depth

Date: 2026-08-04 America/Toronto

> **REFUTED the same day, by building the lever it proposes.** Inlining
> attention retired 48 of the 145 breaks exactly as predicted (146/145 -> 98/97
> on every rank) and measured **+1.8% / -0.5% / +2.4%**, while changing the
> 32,640 token stream. See
> [`2026-08-04-KEY-retiring-48-graph-breaks-bought-2-percent.md`](2026-08-04-KEY-retiring-48-graph-breaks-bought-2-percent.md).
>
> **The topology described below is accurate and worth keeping.** The inference
> drawn from it -- that the 8.1 ms attributed to attention boundaries is
> retirable overhead -- is wrong: that figure is overwhelmingly the attention
> kernel itself, executed eagerly and awaited. A boundary's cost is mostly the
> work it performs.
>
> What survives is narrower and better supported: **every arm that held the
> collective rendezvous count at 97 moved nothing**, including this one, which
> cut total breaks by a third. Rendezvous count, not break count, is the
> untested structural quantity.

Status: **mechanism identified from the code's own audited topology and from
two prior measured runs; the lever it proposed was built and refuted.**

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

## The per-boundary cost was already measured, on 2026-07-25

[`2026-07-25-m8-inprocess-replay-telemetry-result.md`](2026-07-25-m8-inprocess-replay-telemetry-result.md)
timed each boundary in process, max-rank, 31 samples:

| field | median | per call | share of host total |
| :--- | ---: | ---: | ---: |
| whole replay completion | 21.544 ms | | |
| replay host total | 16.724 ms | | 100% |
| **48 attention boundaries** | **8.118 ms** | **169.1 us** | **48.5%** |
| 97 collective boundaries | 6.080 ms | 62.7 us | 36.4% |
| 146 graph replays | 2.097 ms | 14.4 us | 12.5% |
| static-signature validation | 0.360 ms | | 2.2% |

Host submission is **77.6%** of whole replay completion. So the decode step is
not device-bound at all: it is the host walking 291 segments, and **the 48
attention boundaries alone are 8.1 ms of a 21.5 ms replay**.

This also independently corroborates the standalone harnesses, which reached
the same order from a different direction: `bench_laguna_step_floor.py` gives
145 us per layer with collectives removed, and
`bench_laguna_collective_scaling.py` gives ~83 us per collective call.

That note set "reducing host overhead at the 48 attention boundaries" as the
primary lane, but constrained the candidate to preserve "the exact graph
topology". Retiring the boundaries changes the topology to 98/97, which is what
the 2026-07-26 control concluded was necessary once nested capture -- which
preserved topology -- returned 0.53%.

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

Retiring the 48 attention boundaries is a **33% reduction in break count** and,
by the 07-25 telemetry, up to **8.1 ms off a 21.5 ms replay**. The remaining 97
boundaries are collectives at 62.7 us each -- 6.1 ms -- which is where the
sequence-parallel and deferred-reduce ideas apply. The 250 target plausibly
needs both.

Two implementation routes exist, and only one is available:

- **`CUDAGraphMode.FULL`.** `unified_attention_with_output` is decorated
  `break_in_full=False`, so the existing wrapper already inlines it under FULL.
  **Refused**: the breakable-graph contract's `runtime_mode` term is
  `cudagraph_mode != CUDAGraphMode.PIECEWISE`, measured 2026-08-04. FULL is not
  reachable on the candidate path.
- **Inline under PIECEWISE.** Apply the same inlining without changing the
  runtime mode, so dispatch keys and capture sizes are untouched. Built as
  `VLLM_XPU_LAGUNA_M8_INLINE_ATTENTION_GRAPHS`, default off. The harness had
  already reserved this exact selector name and pinned it to 0; vLLM had no
  reader for it.

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
