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

**About 70% of every rendezvous is not data movement.** It is the collective
sitting on the device until the slowest of four ranks arrives.

That single number reconciles every result in the campaign:

- removing 95% of the **bytes** (expert parallelism off) touched only the 72 us
  part, and measured **-4.6%**;
- retiring 48 of 145 **graph breaks** touched neither part, and measured **+2%**;
- halving the **count** of rendezvous removed 48 whole 252 us waits, and
  measured **-18.3%**.

## Where this points

Two independent levers now exist, and the second is new:

1. **Fewer rendezvous.** Replicated attention with expert parallelism only
   removes the 48 attention O-projection gathers outright, for +2.95 GiB per
   rank. Priced at about -18%.
2. **Less skew per rendezvous.** If ~180 us of each 252 us is waiting for the
   slowest rank, the ranks are arriving unevenly. With top-10 routing over 256
   experts on 4 ranks, the per-rank expert count varies every step, so one rank
   is always doing more MoE work than the others and gates the meeting. This
   lever shrinks **all 96** rendezvous rather than removing half.

Lever 2 is the more interesting one because **expert placement is not expert
routing**. Which experts a token selects is fixed by the model and must not
change. Which rank *hosts* a given expert is a deployment choice, and choosing
it so that frequently co-activated experts land on different ranks is
arithmetically neutral -- the same experts run on the same inputs, only on
different devices.

Neither lever is built. Skew has not yet been measured directly; that is the
next measurement, and per-rank arrival timestamps at a few boundaries would
settle it.

## Boundaries

Warm kineto trace from `20260804-warm-kernel-trace`, rank 0, analyzed with
`analyze_laguna_decode_kernel_profile.py` after its two attribution bugs were
fixed (profiler span markers counted as device time, FMHA kernels filed as
gemm). Summed kernel duration is not critical-path time, which is why the
per-call means are quoted rather than the totals, and why the idle allreduce is
excluded. No quantisation change, no caching or speculation setting used to
inflate any number. The protected `125.4619731637751 tok/s` conventional
short-decode record is untouched.
