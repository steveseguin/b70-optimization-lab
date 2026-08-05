# Retiring 48 of 145 graph breaks bought 2%, and broke 32K exactness

Date: 2026-08-04 America/Toronto

Status: **measured, matched control, candidate rejected. This refutes the
lever proposed in
[`2026-08-04-KEY-the-fixed-per-step-cost-is-145-graph-breaks.md`](2026-08-04-KEY-the-fixed-per-step-cost-is-145-graph-breaks.md),
which is corrected in place. The topology facts in that note stand; the
conclusion drawn from them does not.**

## What was built

`VLLM_XPU_LAGUNA_M8_INLINE_ATTENTION_GRAPHS` (default off) records each of the
48 attention calls into its surrounding cudagraph segment instead of ending the
segment, running the op eagerly, and starting a new one. This is the candidate
the 2026-07-26 matched control named after nested attention graphs preserved
all 48 boundaries and returned +0.53%.

It works exactly as predicted. The runtime guard reported the intended shape
before it was taught to expect it:

```
Breakable graph topology changed: saw graphs/eager=(98, 97), expected (146, 145)
```

**146/145 became 98/97 on every rank** -- 48 boundaries retired, a 33%
reduction in break count -- and the server captured, replayed and served
correctly.

## The result

qdepth depth 11, width 12, matched control `20260804-depthwarm-d11`, warm
server, cold prefix cache on every row, all retrieval field checks passing on
both arms:

| case | control | inline | delta | token stream |
| :--- | ---: | ---: | ---: | :--- |
| 8,192 middle | 7.592 | 7.731 | **+1.8%** | identical |
| 32,640 early | 32.102 | 31.931 | **-0.5%** | **differs** |
| 256 sentinel | 131.530 | 134.718 | **+2.4%** | identical |

## Why it is rejected

**Exactness.** `154c7d6e19b3...` is the canonical 32,640 token stream: eight
runs across depth sweeps, EP-on diagnostics, post-reboot verification, the q12
control, the swa4096 drafter arm, the kernel-profile run and the warm sequence
all produce it, including this candidate's own control. The inline arm produced
a hash no other run has. Same profile, same depth, same selector set; inlining
is the only difference. **Recording attention into the graph changes the 32K
result.** That alone disqualifies it, independent of speed.

**And the speed was not there anyway.** ~2% for retiring a third of the
boundaries.

## What this refutes, and the error in it

The 2026-07-25 in-process telemetry measured 48 attention boundary calls at
**8.118 ms**, 48.5% of a 16.7 ms replay host total, and host submission at
77.6% of whole replay completion. I read that as 8.1 ms of retirable boundary
overhead. It is not.

**The 169.1 us per attention boundary is overwhelmingly the attention kernel
itself**, executed eagerly and awaited. Inlining moves that kernel inside the
graph; it does not make it cheaper. What is actually retired is the
segment-switch overhead, and that is worth about 2%.

This is the same error as "collectives are 94% of the step", which removing 95%
of collective bytes measured at -4.6%. **Summed host-call duration attributed
to a boundary is not critical-path time**, and a boundary's cost is mostly the
work it performs, not the fact that it is a boundary. Recorded here as the
sixth instance this session of a hypothesis that survived reasoning and died on
measurement.

## What survives, and where it points

Line up every negative result by what it did and did not change:

| change | breaks | collective rendezvous | bytes | result |
| :--- | ---: | ---: | ---: | ---: |
| expert parallelism off | 145 | **97** | -95% | -4.6% |
| draft depth 11 -> 7 | 145 | **97** | - | -0.6% |
| context 256 -> 32,640 | 145 | **97** | - | small |
| **inline attention** | **97** | **97** | - | **+2%** |
| collective-count sweep (standalone) | - | **96 -> 48** | - | **14.72 -> 11.23 ms** |

Every arm that held the **collective rendezvous count at 97** moved nothing,
including this one, which cut total breaks by a third. The only lever that has
ever moved the standalone floor is **reducing how many times per step the four
ranks rendezvous**.

Attention boundaries are not rendezvous points; collective boundaries are. 97
rendezvous per step, each of which cannot complete until the slowest rank
arrives, is the one structural quantity no experiment has yet reduced in the
real model.

**That is the next candidate, and it is the only one the evidence supports:**
keep activations sharded across several decoder layers and reduce every N
layers rather than every layer. `bench_laguna_collective_scaling.py` already
prices it at 14.72 ms (96 calls) -> 11.23 ms (48) -> 9.42 ms (24).

## Disposition of the code

The selector stays, default off, with the topology expectations that make it
runnable, because it is the only way to measure the boundary-versus-work split
and it produced this result cheaply. It must not be promoted: it is not exact
at 32K.

## Boundaries

Both arms qdepth depth 11 width 12, TP4, util 0.80, EP4, warm server, cold
prefix cache on all rows, identical selector sets otherwise. qdepth disables
most of the incumbent's optimised selectors, so absolute figures sit below q12;
the delta is the result, not the level. No quantisation change, no caching or
speculation setting used to inflate any number. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
