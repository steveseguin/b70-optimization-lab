# Throughput is the goal metric, and it had never been measured

*2026-09-15, packet39 server, `graph-text` arm,
[`scripts/run-throughput.py`](../scripts/run-throughput.py).*

The goal is "generate one second of new video in under one second, **continuously**".
That is a throughput target: the interval between finished clips when they are
produced back to back. Everything in this lane so far -- `preview_ready_seconds`,
every A/B in every packet -- measures single-clip **latency**, which is not the
same quantity and has no reason to equal it.

Six clips queued at once on the current best arm:

| Clip | Finished at | Interval |
| --- | ---: | ---: |
| 00 | 0.000 s | - |
| 01 | 4.916 s | 4.916 s |
| 02 | 9.838 s | 4.921 s |
| 03 | 14.283 s | 4.446 s |
| 04 | 18.885 s | 4.602 s |
| 05 | 23.705 s | 4.820 s |

**Steady-state interval: 4.697 s mean** over the warm clips, for 1.042 s of video
(25 frames at 24 fps).

> **4.51 seconds of compute per second of video. The goal is under 1.00.**

The interval is about 0.19 s longer than the single-clip latency of 4.51 s, which
is per-prompt overhead: ComfyUI runs queued prompts strictly serially, so nothing
overlaps between clips today.

## The one precondition that does hold

Pipelining clip N's decode against clip N+1's sampling needs those two to run
concurrently on different cards. That was measured directly
([`scripts/cross-device-overlap-probe.py`](../scripts/cross-device-overlap-probe.py)),
in the realistic shape -- a captured XPU graph replaying on xpu:0 (almost no
Python) against dispatch-heavy eager work on xpu:3 (lots of Python):

| | alone | together |
| --- | ---: | ---: |
| graph replays, xpu:0 | 0.233 s | |
| dispatch-heavy eager, xpu:3 | 0.427 s | |
| sum | 0.660 s | **0.428 s** |

**100% of the hideable cost was hidden.** The GIL does not serialise them, and
the two cards run genuinely concurrently. So the decode really can be hidden
behind the next clip's sampling; what blocks it is only ComfyUI's single-threaded
prompt worker.

## Where the 4.697 s goes, and the honest ceiling

| Stage | Per clip | Notes |
| --- | ---: | --- |
| Text encode | 1.59 s | once-only in a real stream; the prompt never changes |
| Sampler | 1.93 s | 0.74 s is an irreducible weight-read floor |
| Video decode | 0.53 s | hideable behind the next clip's sampling |
| Audio decode | 0.18 s | hideable |
| Save | 0.13 s | hideable |
| Per-prompt overhead | 0.19 s | |

Taking every identified lossless lever -- caching the conditioning for an
unchanged prompt, overlapping all of decode and save with the next clip's
sampling, and removing every remaining non-GEMM inefficiency in the sampler --
lands near **1.5 s per second of video**. That is a 3x improvement on today and
still **about 1.5x short of the goal**, because the sampler alone cannot go
below its 0.74 s weight-read floor plus whatever of its 0.84 s of non-GEMM work
survives.

## A caveat about "new" video

Every clip in this harness uses the same prompt and the same seed, so the clips
are bytewise identical to each other by design -- that is what makes the
bitwise oracle possible. It also means a pipelining bug that delivered a stale
clip would be **invisible** to the oracle. Any pipelined implementation has to
be validated with per-clip distinct seeds and per-clip pinned references, not
with the current single reference.
