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

### Corrected: token capacity does not scale linearly on a hybrid model

My first pass scaled the reported 91,258 tokens by 1/4 and got 22,814. **That
is wrong.** On a hybrid model the reported token figure is not linear in KV
heads, because full-attention and sliding-attention layers reserve different
numbers of blocks. The right calculation sizes one sequence directly.

From `SlidingWindowSpec.max_admission_blocks_per_request`, blocks reserved per
sliding layer are `cdiv(min(sliding_window - 1 + max_in_flight_tokens,
max_model_len), block_size) + 1`, and `max_in_flight_tokens =
max_concurrent_batches x max_num_batched_tokens = 8192`. So each sliding layer
reserves **137 blocks** against a full layer's 512, at block size 64.

One 32,768-token sequence, per rank:

| | 2 KV heads (today) | 8 KV heads (replicated) |
| :--- | ---: | ---: |
| 12 full layers | 384 MiB | 1,536 MiB |
| 36 sliding layers | 308 MiB | 1,233 MiB |
| **total** | **692 MiB** | **2,769 MiB** |

| configuration | KV budget | needed | verdict |
| :--- | ---: | ---: | :--- |
| today, util 0.80 | 2,960 MiB | 692 | fits, 4.3x |
| replicated, util 0.80 | 2,960 - 3,021 weights | 2,769 | **does not fit** |
| replicated, full utilisation | 7,618 - 3,021 = **4,597 MiB** | 2,769 | **fits, 1.66x** |

The 7,618 MiB figure is the server's own: it reports
`--kv-cache-memory=7989950976 (7.44 GiB) to fully utilize gpu memory` against
the 2.89 GiB it takes at util 0.80.

At util 0.80 the extra **3,021 MiB of replicated attention weights alone
exceeds the entire 2,960 MiB KV budget**, so the configuration is impossible
before KV is even considered. At full utilisation it fits with **1.66x margin**
-- better than the 1.08x I first claimed, but still requiring the GPU to run
with essentially no reserve.

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

### The windowed-layer KV lead -- RETRACTED

**The reasoning below is wrong and is kept only so the mistake is not
repeated.** I inferred that windowed layers "should" cost 0.016 of a full layer
because a 512-token window holds 512 of 32,768 positions, and called the
measured share waste.

`SlidingWindowSpec.max_admission_blocks_per_request` shows it is not waste. A
sliding layer must hold `sliding_window - 1 + max_in_flight_tokens` tokens,
because during chunked prefill out-of-window blocks are freed on the
processed-token basis and in-flight steps transiently keep theirs. With
`max_in_flight_tokens = 8192` that is 8,703 tokens, or **137 blocks** -- a
principled reservation, not an over-allocation.

It *is* reducible, but only by shrinking `max_num_batched_tokens`: at 512
in-flight a sliding layer needs 17 blocks and one sequence drops from 692 to
422 MiB. That value is contract-pinned to the 8,182-token prefill partition,
and prefill currently measures 7,505 tok/s against a 7,000 floor -- so trading
it for KV would put a met target at risk. Not recommended.

### Original reasoning, retained as the error

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
