# Consolidated: three decode targets, one root cause

> **SUPERSEDED 2026-08-04.** The central claim below -- that MoE all2all is the
> root cause and that TP-sharding the experts would recover most of the decode
> step -- was **measured and refuted**. With an identical kernel package and only
> `--no-enable-expert-parallel` differing, warm 32K decode went **38.829 -> 37.027**,
> i.e. removing the all2all made decode **4.6% slower**. See
> [`2026-08-04-MEASURED-expert-parallelism-is-not-the-lever.md`](2026-08-04-MEASURED-expert-parallelism-is-not-the-lever.md).
>
> What survives: the measured breakdown itself, the volume arithmetic, the
> collective floor, and the method notes at the end. What does not: every
> inference that treated summed collective device time as recoverable wall clock,
> including the "~94% of the step" headline and the work ordering built on it.
>
> The surviving explanation for the 32K target is drafter acceptance
> ([`2026-08-04-the-32k-target-is-blocked-by-the-drafter.md`](2026-08-04-the-32k-target-is-blocked-by-the-drafter.md)).

Date: 2026-08-04 America/Toronto

Status: **synthesis of the 2026-08-04 measurements. Read this first; the
individual notes carry the evidence.**

## Where the targets stand

| target | measured | verdict |
| :--- | ---: | :--- |
| 1000 tok/s prefill | **7,340.6** at 32,640 warm | **met** |
| >150 tok/s at 32K with speculation | 39.848 | not met |
| 250 tok/s with speculation | 163.566 at 256 tokens warm | not met |
| 100 tok/s without speculation | 13.31 | **unmeasured** on the optimized path |

## The step is ~90% MoE all2all at every context

The warm trace at 32,640 tokens, 2.7% perturbation, gives per decode step:

```
oneccl_allgatherv_pcie   98 calls  p50 205 us   24.7 ms   ~94%
oneccl_allreduce_pcie    13 calls  p50 138 us    5.5 ms
attention (cutlass FMHA) 67 calls                1.27 ms    5%
gemm_kernel               4 calls                0.73 ms    3%
```

Device kernel time excluding collectives is **~2.2 ms of a ~26.4 ms step**.

The same holds at short context. Warm step times are **22.4 ms at 256 tokens**
and **26.5 ms at 32,640** -- only 4 ms apart, and that 4 ms is attention over a
128x longer KV. The all2all payload is set by `M x top-k x hidden`, which does
not depend on context at all, so the ~24.7 ms is present in the 256-token step
too. **Short-context decode is collective-bound for the same reason long-context
decode is.**

That is why the 250 target and the 150-at-32K target are the same problem.

## The transport is fine; the volume is not

| quantity | value |
| :--- | ---: |
| in-situ allgatherv | 205 us |
| standalone at the same 1.44 MB payload | 225 us |
| ingress per rank (3 peers x 1.44 MB / 225 us) | **19.66 GB/s** |
| measured PCIe H2D on the same cards | 28.70 GB/s |
| fraction of PCIe achieved | **69%** |

Nine oneCCL/libfabric configuration arms move this by at most 3%, including at
the correct payload size. DeepEP and pplx are not installed; `naive` and `pplx`
fall back upstream; the MPI transport needs `mpiexec`. **Configuration is
exhausted, and there is nothing being left on the table by the transport.**

Volume is the whole story:

| scheme | per layer | per step |
| :--- | ---: | ---: |
| EP all2all (today) | 1.475 MB | ~70.8 MB |
| TP all-reduce | 0.074 MB | 3.54 MB |

**20x.**

## One root cause behind three unmet targets

The optimized kernels are specialised to exactly `(M=12, DFlash depth 11, EP4)`
and refuse to load otherwise. Five interlocking gates enforce it: the launcher's
q12 profile, the shared-elementwise parallel-identity contract, both
breakable-graph validators, the batched-exact MoE assert
(`local_experts=64, ep_size=4, intermediate_size=1024`), and the BF16 router
top-k which depends on the fourth.

Consequences, each measured rather than assumed:

- **>150 at 32K** is blocked because cutting the all2all requires TP-sharded
  experts, which gate 2-5 forbid.
- **250 with speculation** is blocked by the same all2all, present at short
  context too.
- **100 without speculation** is *unmeasured*: the contract requires DFlash
  depth 11, so removing speculation removes the kernels. 13.31 is a lower bound
  from a generic path, evidenced by being flat within 2% across a 128x context
  range and across cold/warm, which no real workload is.

And the specialisation buys little: with `VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=0`
and expert parallelism still on, warm 32K decode is **39.403** against **39.848**
for the full stack -- **~1%**. The kernel whose contract mandates EP4 across the
entire stack is worth about one percent, while the expert parallelism it
enforces costs ~94% of the step.

## The work, in one sentence

**De-specialise the fast path** -- support `M=1` and a TP-sharded expert layout
in the shared-elementwise kernel, the batched-exact MoE kernel and the BF16
router top-k -- and three of the four targets become reachable or, for the
no-speculation case, measurable for the first time.

Sub-order within that work:

1. TP-shard the experts (the 20x volume reduction; largest quantified win).
2. Support `M=1` on the fast path (makes the no-speculation target real).
3. Only then re-derive what remains; the acceptance ceiling
   ([`2026-08-04-the-32k-target-is-blocked-by-the-drafter.md`](2026-08-04-the-32k-target-is-blocked-by-the-drafter.md))
   becomes the binding constraint at 32K once communication stops dominating.

Explicitly **not** worth doing, each closed by measurement today: oneCCL and
libfabric tuning (<=3%), alternative all2all backends (unavailable), deeper
drafts (+2.5%), widening the draft window (acceptance got worse), investigating
the fabric ceiling (69% of PCIe already), and overlapping collectives with
compute (~24.7 ms of communication against ~2.2 ms of compute to hide it
behind).

## Method notes that cost real time today

- The campaign's headline numbers are **warm-server** measurements. A single-case
  run measures a **first** request and pays ~5.5 s of fixed warmup; comparing the
  two produced a phantom 5x regression and an unnecessary reboot. Reproduce the
  baseline's case order.
- A profiled trace on this stack costs ~2.7% when taken warm, not the 6x first
  reported. Check any diagnostic run's own throughput against baseline before
  trusting its attribution.
- Benchmark the payload the system actually moves. The 72 KiB standalone figure
  supported a confident "latency-bound" conclusion that was wrong; at the real
  1.44 MB the same harness reproduces the trace within 10%.

## Boundaries

All figures cold prefix cache, TP4, util 0.80, no quantisation change, no
caching or speculation setting used to inflate any number. Warm and cold are
labelled throughout. The protected `125.4619731637751 tok/s` conventional
short-decode record is untouched.
