# Replicated attention costs 4x KV, and only fits at near-full utilisation

Date: 2026-08-04 America/Toronto

Status: **feasibility check on measured server numbers, before building
anything. It narrows the one validated lever from "buildable" to "marginal",
and the constraint is KV capacity rather than weight memory.**

## Why it looked cheap

[`2026-08-04-KEY-q12-rendezvous-halving-is-worth-22-percent.md`](2026-08-04-KEY-q12-rendezvous-halving-is-worth-22-percent.md)
prices halving the gathers at **-21.7%** of the q12 decode step, and the exact
way to remove 48 of the 96 is to replicate attention so its O projection needs
no collective. I sized that at **+2.95 GiB per rank** of attention weights and
called it affordable.

**That sizing was incomplete.** It counted the weights and not the KV cache.

## The constraint

Laguna has 48 query heads and **8 key/value heads**. TP4 gives each rank **2 KV
heads**. Replicating attention gives each rank **all 8** -- so the KV cache per
token is **4x** larger, on every layer, for the whole context.

Measured from the q12 server at util 0.80, per rank:

| quantity | value |
| :--- | ---: |
| available KV cache memory | **2.89 GiB** |
| KV cache size | **91,258 tokens** |
| implied per token, 2 KV heads | 33.2 KiB |
| implied per token, 8 KV heads | 132.8 KiB |
| GPU physical memory | 31.9 GiB |

| configuration | KV budget | capacity | vs 32,768 required |
| :--- | ---: | ---: | :--- |
| today, util 0.80 | 2.89 GiB | 91,258 | 2.8x headroom |
| replicated, util 0.80 | 2.89 GiB | **22,814** | **does not fit** |
| replicated, full utilisation | 7.44 - 2.95 = 4.49 GiB | **~35,447** | 1.08x |

The 7.44 GiB figure is the server's own: it reports
`--kv-cache-memory=7989950976 (7.44 GiB) to fully utilize gpu memory` against
the 2.89 GiB it takes at util 0.80.

## Reading it

**Replicated attention does not fit at the current operating point.** It fits
only if GPU utilisation is pushed from 0.80 to essentially 1.0, and even then
capacity is ~35.4K tokens against the 32,768 the suite requires -- an **8%
margin**.

That margin is survivable *only* because the breakable-graph contract pins
`max_num_seqs = 1`, so exactly one sequence occupies the cache. Any concurrency
at all, or any future context beyond 32K, breaks it.

So the honest status of the session's one validated lever is:

- worth **-21.7%** of the step, projecting 162.0 -> ~207 tok/s;
- **arithmetically exact** and quality-neutral;
- **not** blocked by the compiled-in `num_local_experts == 64` gate;
- but **requires running the GPU at near-full utilisation with 8% KV headroom**,
  which is a real deployment risk on a system the campaign has already had to
  recover from wedges several times.

## What would make it comfortable

- **Replicate attention over pairs instead of all four ranks.** 4 KV heads per
  rank rather than 8, so 2x KV instead of 4x and +0.98 GiB of weights. But the
  attention gather then runs among 2 ranks instead of vanishing, and **count is
  the lever, not participants**, so this likely recovers little. Cheap to test
  with the existing skip diagnostic before building.
- **Shrink KV on the windowed layers.** This is the first thing to check, and
  the arithmetic says it is large.

### The windowed-layer KV lead

One full-attention layer costs `2 (K,V) x 2 KV heads x 128 x 2 bytes` =
**1.00 KiB per token** per rank. Laguna has **12 full-attention layers and 36
sliding-attention layers with a 512-token window**. So:

| | KiB/token | implied share per sliding layer |
| :--- | ---: | ---: |
| 12 full layers alone | 12.0 | -- |
| all 48 layers as full | 48.0 | 1.000 |
| **measured** | **33.2** | **0.589** |
| a 512 window over 32,768 | 12.6 | 0.016 |

The windowed layers are being charged **0.589 of a full layer each**, against a
window that can only ever hold 512 of 32,768 positions. Whatever the allocator
is doing, it is not sizing them to their window.

| configuration | KiB/token | capacity | replicated (4x) |
| :--- | ---: | ---: | ---: |
| today | 33.2 | 91,277 | 22,819 (**short**) |
| windowed layers sized to their window | **12.6** | 241,225 | **60,306** |

**If that headroom is real, replicated attention fits at util 0.80 with 1.84x
margin over the required 32,768**, and the near-full-utilisation risk above
disappears entirely. It is also quality-neutral by construction: a
sliding-attention layer cannot attend outside its window, so storing more of
the context for it changes no arithmetic.

This is **arithmetic on reported numbers, not a measurement**, and vLLM's
hybrid KV allocator is subtle -- speculative decode needs window plus draft
depth, and block granularity is 64. Verify against
`kv_cache_config` before believing it. But a 0.589-versus-0.016 gap is large
enough that even a partial reclaim changes the feasibility verdict.

## Boundaries

Numbers read from the `20260804-eventprofile-q12` server log, util 0.80, TP4,
EP4, 32,768 max model length, `max_num_seqs=1`. The capacity figures for
replicated attention are arithmetic on those measurements, not measurements. No
quantisation change; reducing KV precision is explicitly not proposed. The
protected `125.4619731637751 tok/s` conventional short-decode record is
untouched.
