# Warm trace: 32K decode is ~94% MoE all2all, and expert parallelism is the cause

Date: 2026-08-04 America/Toronto

Status: **measured on a warm server with 2.7% profiler perturbation. This is the
first trustworthy kernel attribution in the campaign; it supersedes every
earlier attribution, all of which were taken cold and/or heavily perturbed.**

## Why this trace can be believed

Previous traces were taken on a **first request**, which costs ~5.5 s of warmup
and made the profiler look 6x more expensive than it is (see
[`2026-08-04-RETRACTION-there-was-no-regression.md`](2026-08-04-RETRACTION-there-was-no-regression.md)).
This capture ran an 8K case first to absorb the warmup, then profiled 15 decode
steps inside a warm 32,640-token request:

```
profiled   38.760 tok/s
unprofiled 39.848 tok/s      -> 2.7% perturbation
```

15 events longer than 1 second were discarded. There is exactly one per captured
iteration and the longest is 55 s, which is impossible inside a 3.3 s decode
phase; they are rank-idle artifacts spanning the capture boundary, not work.

## The breakdown, per decode step at 32,640 tokens

| kernel | calls/step | p50 | per step | share |
| :--- | ---: | ---: | ---: | ---: |
| **`oneccl_allgatherv_pcie`** | **98** | **205 us** | **24.7 ms** | **~94%** |
| `oneccl_allreduce_pcie` | 13 | 138 us | 5.5 ms | -- |
| attention (cutlass FMHA) | 67 | 18.6 us | 1.27 ms | 5% |
| `gemm_kernel` | 4 | 267 us | 0.73 ms | 3% |

**Device kernel time excluding collectives is ~2.2 ms per step**, against a step
of ~26.4 ms. Compute and memory bandwidth are not the constraint and never were.

## The payload was 19x larger than the standalone benchmark assumed

The standalone benchmark measured 45.9 us per allgather and concluded the
collectives were latency-bound. In situ they take **205 us**. Interpolating that
benchmark's own size curve (72 KiB -> 45.9 us, 1152 KiB -> 175 us, 4608 KiB ->
689 us) puts 205 us at roughly **1.4 MB per call**, not 72 KiB.

That is exactly MoE dispatch. With top-10 routing at M=12:

```
12 tokens x 10 experts x 3072 hidden x 2 bytes = 737 KB   dispatch
                                       x 2     = 1.475 MB dispatch + combine
                                       x 48 layers = 70.8 MB per step
```

The earlier "latency-bound, config tuning exhausted" conclusion was answering the
wrong question: the collectives are **bandwidth**-bound on a fabric that
delivers 6.85 GB/s, and the volume is set by expert parallelism.

## Expert parallelism is the lever, quantified

Expert parallelism sends each token's hidden state to all 10 of its routed
experts across ranks. Tensor-parallel sharding of the experts instead requires
only an all-reduce of the hidden state:

| scheme | per layer | per step | at 6.85 GB/s |
| :--- | ---: | ---: | ---: |
| EP all2all (today) | 1.475 MB | 70.8 MB | 10.3 ms (trace shows 24.7) |
| TP all-reduce | 0.074 MB | 3.54 MB | 0.52 ms |

**A 20x reduction in collective volume.** The measured 24.7 ms exceeds the
70.8 MB model, most likely because an allgather across four ranks delivers the
gathered result to every rank; the direction is robust regardless of that factor.

## What it is worth, stated honestly

If collectives dropped to the TP figure and nothing else changed, the step would
fall from ~26.4 ms toward the ~2.2 ms of non-collective kernel time, implying
several hundred tok/s. **That number should not be quoted.** It ignores
per-collective latency floors, host overhead, and the extra compute each rank
performs when experts are TP-sharded rather than EP-partitioned.

A defensible range: removing the all2all replaces ~30 ms of communication with
roughly 0.5-2 ms, giving a step of perhaps **4-8 ms, i.e. 130-260 tok/s** at
32,640 tokens. Even the pessimistic end reaches the >150 tok/s target that was
re-scoped away earlier today on the belief that acceptance was the only lever.

Note this does **not** contradict the acceptance finding: at 32K the drafter
contributes ~1.08 tokens/step, and that stays true. What changes is the time per
step, which is the other factor in the same product.

## The blocker, and why it is now worth paying

`--no-enable-expert-parallel` currently fails: the M12 shared-elementwise kernel
is built around the expert-parallel layout and the engine refuses to start
without it. Teaching that kernel a TP-sharded layout is real work, and it was
twice deprioritised in this campaign -- once on the assumption that expert
parallelism was free, and once on a corrected-but-still-wrong estimate that
collectives were ~19% of the step.

On this measurement they are ~94%. **This is the single highest-value piece of
decode work available**, and it does not touch quantisation, speculation, or
output quality.

## Boundaries

Warm server, cold prefix cache, TP4, util 0.80, q12, depth 11, no quantisation
change, no caching or speculation setting used to inflate any number. Profiler
perturbation measured at 2.7% against the unprofiled run in the same
configuration. The volume arithmetic is arithmetic; the tok/s range is an
estimate and is labelled as one. The protected `125.4619731637751 tok/s`
conventional short-decode record is untouched.
