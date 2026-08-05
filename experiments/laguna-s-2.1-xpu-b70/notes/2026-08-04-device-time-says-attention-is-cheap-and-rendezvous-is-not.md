# Device time: attention is ~19 us a call, each rendezvous is ~252 us

Date: 2026-08-04 America/Toronto

Status: **measured from the warm kineto trace with the corrected analyzer.
Refutes my own inference that the attention kernel costs ~155 us, and gives the
rendezvous a device-side price.**

## The inference this replaces

The 07-25 host-call telemetry attributed **169.1 us** to each attention
boundary. Inlining attention retired all 48 boundaries and saved only ~14 us
each, so I concluded the remaining ~155 us was the attention *kernel*.

Device time says otherwise.

## What the device actually runs

Warm trace, rank 0, host categories excluded:

| kernel | device time | calls | mean |
| :--- | ---: | ---: | ---: |
| `oneccl_allgatherv_pcie` | 370.261 ms | 1,470 | **251.9 us** |
| `XeFMHAFwdSplitKVKernel` (a) | 10.071 ms | 540 | **18.6 us** |
| `XeFMHAFwdSplitKVKernel` (b) | 7.994 ms | 180 | 44.4 us |
| `gemm_kernel` | 11.022 ms | 60 | 183.7 us |
| `ReduceSplitK` | 0.997 ms | 180 | 5.5 us |

By role: **collectives 820.6 s, attention 19.2 ms, gemm 11.0 ms**, elementwise
2.2 ms, norm 0.2 ms.

**Attention is ~19 us per call on the device**, not 155. All attention in a
decode step is roughly **1.25 ms**, against a step of 28-33 ms. Attention is not
the lever, and the kernel does not need rewriting.

The single `oneccl_allreduce_pcie` line at a 3.9 *second* mean over 210 calls is
the **idle barrier between requests**, not decode work; it is what makes the
collective role total 820 s and device occupancy read 99.9%. It must not be
counted as step cost. This is the same trap as the 94%-collective-bound reading:
a rank inside a collective is usually waiting.

## The rendezvous price

96 gathers per step at 251.9 us is **~24 ms of device occupancy per step**,
which is the same order as the whole step. Against that:

| quantity | value |
| :--- | ---: |
| real payload | 1.44 MB |
| measured ingress | ~20 GB/s |
| **transfer time implied** | **~72 us** |
| **measured per-call device time** | **~252 us** |
| **remainder** | **~180 us** |

I first read the ~180 us remainder as **rank arrival skew** and built an
expert-placement lever on it. **That does not survive my own earlier standalone
measurement**, and is retracted here rather than left to propagate.

`bench_laguna_xccl_allgather.py`, four ranks in a tight loop with negligible
skew, at the real 1.44 MB payload: **225 us standalone, 205 us in situ**, an
ingress of **19.66 GB/s, which is 69% of PCIe**. An allgather over four ranks
moves 3x the payload into each rank, so 1.44 MB x 3 = 4.32 MB in 225 us is
19.2 GB/s -- the same figure.

**So ~252 us is close to what this collective costs on this fabric with no skew
at all.** The naive 72 us was wrong because it counted the payload once rather
than the (world-1) copies an allgather actually ingests.

## An unresolved conflict, stated rather than papered over

Two measurements disagree about whether **bytes** matter:

- the standalone benchmark says the collective runs at **69% of PCIe**, i.e.
  bandwidth-limited, so bytes should dominate;
- disabling expert parallelism removed ~95% of collective bytes and measured
  **-4.6%**.

Both cannot be straightforwardly true. Possible resolutions, none established:
the EP-off arm replaced an allgather with an allreduce whose own traffic is
comparable; the EP-off arm paid an unfused generic MoE cost that masked a real
collective gain; or in situ the collectives overlap enough that their bandwidth
is not on the critical path.

### It resolves with the arms already run

The two existing arms happen to separate the variables:

| arm | bytes | count | result |
| :--- | :--- | :--- | ---: |
| expert parallelism off | **-95%** | held at 97 | **-4.6%** |
| gather skip modulus 2 | halved | **halved** | **-18.3%** |

Bytes alone are worth about **4.6%** for a 95% reduction. Count and bytes
together are worth 18.3%, so **count carries roughly 14 of those points**.

That reconciles the standalone benchmark with the in-situ behaviour without
contradiction: standalone, a collective in a tight loop has nothing to overlap
with, so it runs at its bandwidth limit of 69% of PCIe. In situ it overlaps
compute, so most of its transfer is hidden and what remains on the critical
path is the **per-call fixed cost**. That is why bytes barely move the step and
call count moves it a lot.

The prediction this makes is testable: step time should fall roughly linearly
in gather count, not in gather bytes. Modulus 4 would confirm it.

## Where this points

One lever is supported by the evidence, and it is the count:

**Fewer rendezvous.** Replicated attention with expert parallelism only removes
the 48 attention O-projection gathers outright, for +2.95 GiB per rank.
Measured at -18.3% on qdepth and corroborated by the standalone floor sweep at
-23.7%. Notably this does **not** hit the compiled-in EP4 gate: it keeps 64
local experts per rank, and gate 7 in
[`2026-08-04-FINAL-the-ep4-partition-is-compiled-in.md`](2026-08-04-FINAL-the-ep4-partition-is-compiled-in.md)
constrains `num_local_experts`, not which ranks hold attention.

The next measurement should settle the bytes-versus-count conflict directly:
run the gather-skip diagnostic at modulus 2 and 4 on the same profile. If step
time falls linearly with count, count is the lever and bytes are incidental.

## Boundaries

Warm kineto trace from `20260804-warm-kernel-trace`, rank 0, analyzed with
`analyze_laguna_decode_kernel_profile.py` after its two attribution bugs were
fixed (profiler span markers counted as device time, FMHA kernels filed as
gemm). Summed kernel duration is not critical-path time, which is why the
per-call means are quoted rather than the totals, and why the idle allreduce is
excluded. No quantisation change, no caching or speculation setting used to
inflate any number. The protected `125.4619731637751 tok/s` conventional
short-decode record is untouched.
