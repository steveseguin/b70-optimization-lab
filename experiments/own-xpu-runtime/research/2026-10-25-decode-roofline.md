# SC117 decode roofline and what it means for four cards (2026-10-25)

Engine `3108b3c6` (32.04 tok/s exact). The device profile was taken with `OWNRT_DECODE_PROFILE=2`; it is
[profiles/3108b3c6-decode-device-rank0.jsonl](../gsq-rco-iq3s/service-speed/b-prefill/profiles/3108b3c6-decode-device-rank0.jsonl).
The tool is [engine/tools/roofline.py](../engine/tools/roofline.py). Weight bytes come from `loader/placement.tsv`, with
routed experts counted at 10/512 of each tensor. The B70 bandwidth peak is taken as 537 GB/s.

## Rank 0 (layers 0–23), one target step

- Busy: 19.3 ms.
- Matrix kernels: **14.6 ms for 2.35 GB of weights**. At peak bandwidth that would take 4.4 ms, so matrix kernels run
  at 30% of peak.
- Everything else: 4.7 ms (GDN, route, norms, QSA select, HC mix and combine, status checks, activations).

| Site | µs/step | GB/s | µs lost against peak |
|---|---:|---:|---:|
| routed IQ4_NL expert down | 2039 | 77 | 1747 |
| BF16 HC attn/ffn low (2 sites) | 2105 | 150 | 1519 |
| routed IQ2_S expert gate+up | 1831 | 80 | 1557 |
| routed IQ3_XXS expert gate+up | 1056 | 95 | 869 |
| BF16 HC attn/ffn gate (2 sites) | 1374 | 229 | 788 |
| routed Q2_0 expert down | 576 | 56 | 516 |
| Q6_K GDN qkv | 1015 | 297 | 454 |
| Q8_0 shared-expert down | 511 | 82 | 433 |

The expert kernels run at 56–96 GB/s, 6–10× below the bandwidth peak.

## Why: instruction count, not bandwidth or latency

The microbenchmark is [kbench/experts.cpp](kbench/experts.cpp): IQ2_S, 10 slots × 640 × 2560, cold weights, and every
variant bitwise-equal to an exact replica of the engine kernel.

| Variant | µs |
|---|---:|
| exact engine replica (`MultiplyBlockRows<4>`) | 80.1 |
| codebook in local memory | no change |
| software prefetch of the next chunk's bytes | slower |
| gate+up fused into one launch (20 slots) | exactly 2× one launch: throughput-bound |
| full 8-column chunks as a fixed-trip unrolled body | 48.6 |
| plus hoisted row pointers and a 32-bit column index | 43.8 |
| plus **no 64-bit integer → float conversion** (`float(uint64 & 255)` → `float(uint32(...))`) | **33.5** |

The B70 emulates 64-bit integer arithmetic and 64-bit → float conversions. The IQ2_S decoder converted a `uint64_t`
codebook byte for every weight. The second waste was the IQ4_XS decoders (gsq packed and dense block): they index a
local `levels[]` array, which lowers to private memory. The IQ4_NL kernel had already shown this once.

Engine changes in builds `pf29`–`pf33` (serving binary `8476902a`):
- The IQ2_S cast.
- The lean loop in `MultiplyBlockRows`: IQ2_S, IQ3_S, IQ4_NL, Q8_0 and Q6_K routed.
- The lean loop in the raw BF16/F16/F32 `dot` for F32 activations: the HC matrices.
- The lean loop in `lane_dot`.
- The lean loop in the IQ3_XXS block kernel.
- The lean loop in the gsq packed rows kernel: Q2_0 and IQ4_XS routed.
- Register IQ4_XS levels in the gsq and dense-block decoders.
- 32-bit in-block indices in `element_unchecked`.

The arithmetic is unchanged everywhere: the same values in the same order.

## Result (2026-10-25, engine `8476902a`)

Exact on every gate:
- full target state against the F32 oracle: zero differences on both ranks;
- batched prefill gate: 13/13;
- 12-prompt suite: all 12 output hashes identical to `3108b3c6`, MTP hits 4568/5954 unchanged.

**Suite median decode: 32.04 → 37.63 tok/s (+17%).** Rank 0 busy per target step: 19.3 → 15.5 ms. Per-site deltas are
in `profiles/*-decode-device-rank0.jsonl`, produced with `engine/tools/roofline.py --compare`.

| Site (rank 0, µs/step) | `3108b3c6` | `8476902a` line |
|---|---:|---:|
| IQ4_NL expert down | 2039 | 1135 |
| IQ2_S expert gate+up | 1831 | 903 |
| BF16 HC low (2 sites) | 2105 | 1093 |
| BF16 HC gate (2 sites) | 1374 | 1155 |
| Q2_0 expert down | 576 | 415 |
| Q8_0 shared-expert down | 511 | 372 |
| BF16 router | 324 | 212 |

Lessons:
- The 64-bit trap is generic. Keep column and block indices 32-bit, and convert bytes to float through `uint32_t`.
- Do not apply it blindly. In the dense-block kernel a 32-bit block loop and the register IQ4 levels were *slower*
  (IQ4_XS +58%, Q4_K/Q5_K +10%), most likely because a 32-bit unsigned induction variable blocks pointer strength
  reduction. That kernel was reverted to its original code.
- A 64-bit variable shift is emulated as well. Packing the IQ4 levels into two 64-bit words cost more than the 32-bit
  word select (`iq3::iq4_level`).
- Negative: an exact head-shared GDN kernel (8 subgroups × 4 rows per work-group, head values computed once) was
  slower, 933 → 1397 µs. It runs 1536 subgroups of serial row chains, against 6144 independent ones. The patch is
  kept: `profiles/negative-gdn-head-shared-8sg.patch`. The decode GDN runs on the generic `ng` path (dispatch class
  `packet18`), not the `round2` or `specialised` kernels.

## Four cards: corrected estimate

Today's two cards already run as a two-stage MTP pipeline, and both stay busy: rank 0 is busy 19.3 ms of each step.
Measured against that, not against one card's work:
- **Four-stage pipeline, 4 × 12 layers.** Little decode gain for one user, because the stages wait on each other.
  Batched prompt reading gains.
- **TP4-exact** (row splits plus expert placement; small ops replicated on every card). Per card per token, roughly
  0.35/4 + 0.30/3 + 0.30 + 0.05 = 0.54 of one card's whole-model work, plus about 2 ms of synchronization.
  - Today's pipeline needs about 0.5 of it per card.
  - So TP4-exact alone gains little or nothing, and the replicated small ops (30%) dominate.
- **Hybrid** (two pipeline stages × exact two-way split per stage). Per stage per card: 0.175 + 0.19 + 0.30 + 0.05 ≈ 0.71
  of today's stage work, plus about 1 ms of synchronization. That is about **1.3×**.

The single-card matrix kernels are at 30% of peak bandwidth. Raising them toward 60% would cut rank 0's step from
19.3 ms to about 12 ms (**≈1.6×**). That gain multiplies with any card count. Every TP plan also replicates the small
ops, so cheaper small ops raise each plan's ceiling.

Order:
1. Exact kernel efficiency across all formats (this note).
2. Small-op cost.
3. The hybrid four-card layout once cards 27/43 are free; its exact two-way split is built and verified on today's two
   cards.
