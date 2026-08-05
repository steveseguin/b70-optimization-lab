# At the q12 operating point, halving the gathers is worth 21.7% of the step

Date: 2026-08-04 America/Toronto

Status: **measured on the record-relevant profile against a same-session q12
baseline. The candidate arm is deliberately inexact; its throughput is not a
rate Laguna can achieve. Three independent instruments now agree on the
lever.**

## The same-session q12 baseline

Every delta earlier today rode on `qdepth`, which deliberately disables most of
the incumbent's selectors. This run establishes the incumbent afresh, status
**PASS**:

| case | conv99 tok/s | prefill tok/s |
| :--- | ---: | ---: |
| 8,192 middle | 7.855 | 1,046 |
| 32,640 early | **38.425** | **7,505** |
| 256 sentinel | **162.029** | -- |

Consistent with the campaign's standing 163.57 / 39.85.

## The measurement

`VLLM_XPU_LAGUNA_GATHER_SKIP_MOD=2`, q12, everything else identical. Step time
from mean inter-token latency, because the diagnostic drives acceptance to
~100% and makes emission bursty:

| case | tok/step | step ms, q12 | step ms, mod2 | delta |
| :--- | ---: | ---: | ---: | ---: |
| 256 sentinel | 3.657 -> 10.667 | **25.82** | **20.21** | **-21.7%** |
| 32,640 | 1.058 -> 10.667 | 32.73 | 938.54 | unusable |

Long-context rows are unusable under this diagnostic: garbage activations
change generation dynamics enough that the derived step time is meaningless.
The same happened to the 8,192 row on qdepth. Only short context is quoted.

## It saturates at half, which caps the lever

Modulus 4 removes 72 of the 96 gathers rather than 48. It bought nothing more:

| gathers per step | step ms | vs base |
| ---: | ---: | ---: |
| 96 (baseline) | 25.82 | -- |
| **48** (modulus 2) | **20.21** | **-21.7%** |
| 24 (modulus 4) | 20.25 | -21.6% |

Removing the first 48 gathers is worth 5.6 ms. Removing 24 more is worth
**zero**.

This is not a payload effect: every one of the 96 gather buffers is the same
shape, `(TP=4, rows=12, hidden=3072)` bfloat16 = **288 KiB**, allocated
uniformly in `laguna_m8_collectives.py`. Attention-O and MoE-combine gathers
move identical bytes.

The plateau means the gathers **stop being the binding constraint** once about
half are gone, and a **~20.2 ms floor of non-collective work** takes over.

Two consequences, and the first is good news for the planned change:

- **The lever is fully captured by removing half.** Replicated attention
  removes the 48 attention-O gathers, leaving one gather per layer -- the same
  structure modulus 2 produced. It should land on the same ~20.2 ms floor.
- **21.7% is the ceiling for all collective work combined.** Even eliminating
  every gather cannot beat ~20.2 ms. Anything past ~207 tok/s has to come from
  the floor itself, not from the collectives.

## Three instruments, one answer

| instrument | change | step-time effect |
| :--- | :--- | ---: |
| `bench_laguna_collective_scaling.py`, standalone | 96 -> 48 calls | -23.7% |
| gather-skip modulus 2, qdepth | 96 -> 48 gathers | -18.3% |
| **gather-skip modulus 2, q12** | 96 -> 48 gathers | **-21.7%** |

Against everything else tried this session -- collective bytes -4.6%, graph
breaks +2%, draft depth -0.6% -- this is the only structural quantity that has
moved the step, and it has now moved it three times.

## What the honest version is worth

The 96 gathers are 48 attention O projections, 1 dense MLP down, and 47 MoE
final combines. **Replicated attention with expert parallelism only** removes
exactly the 48 attention gathers: each rank holds all attention weights, so the
O projection needs no collective at all. That is the same 96 -> 48 the
diagnostic emulates, but arithmetically exact.

| quantity | value |
| :--- | ---: |
| extra attention weight per rank | **+2.95 GiB** |
| step time, projected | 25.82 -> 20.21 ms |
| **short-context decode, projected** | **162.0 -> ~207 tok/s** |

It does **not** collide with the compiled-in EP4 gate. Gate 7 in
[`2026-08-04-FINAL-the-ep4-partition-is-compiled-in.md`](2026-08-04-FINAL-the-ep4-partition-is-compiled-in.md)
constrains `num_local_experts == 64`; replicating attention leaves the expert
partition untouched at 64 per rank.

## Against the targets

| target | now | with this lever | still short by |
| :--- | ---: | ---: | ---: |
| 250 short context | 162.0 | **~207** | 1.21x |
| 200 at 32,640 | 38.4 | ~38.4 | 5.2x |
| 85 no speculation | 12.1-12.3 | -- | ~7x |
| prefill > 7,000 | **7,505** | -- | **met** |

The short-context target becomes plausibly reachable for the first time: ~207
from this lever, with the remaining 21% needing either the residual segment
overhead (~4.1 ms of the step, 291 segments at ~14 us) or better acceptance.

**32,640 is untouched by any of this.** At 1.058 tokens per step it is gated by
acceptance, not by step time, and no rendezvous work reaches 200 tok/s there.

## Boundaries

q12, depth 11, width 12, TP4, util 0.80, EP4, warm server, cold prefix cache,
baseline `20260804-eventprofile-q12` from the same session and stack. The
candidate arm computes the wrong answer on purpose to price a structural
quantity: its retrieval checks fail, its acceptance is meaningless, and its
throughput must never be quoted as an achieved rate. The projection holds
tokens per step fixed and assumes the exact change costs what the diagnostic
emulates; it is arithmetic on measurements, not a measurement. No quantisation
change. The protected `125.4619731637751 tok/s` conventional short-decode
record is untouched.
