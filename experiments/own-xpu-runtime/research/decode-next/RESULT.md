# Decode next (rank 1): profile of the live engine, and exact levers measured end to end (2026-10-26)

**Engine.** Canonical `engine/src` equals the live service engine 25b3f7542cad:
- reference binary `/dev/shm/engine-build-svc-b15-split23-20261026/sc117-engine`;
- its 244 source hashes match canonical.

**Lab.** `/dev/shm/ownrt-lab-dnext/engine` is canonical plus the lab-only profiling deferral
(`research/decode-experts/profile-defer-lab.patch`).

**Runs.**
- Rank 1 alone on card 27, through `tp_rank1_driver.py` only, under `flock /dev/shm/card27.lock`.
- Launch: the `/dev/shm/ownrt-lab-b13/launch-all.json` template with:
  - the live environment (`OWNRT_ATTN_HEADS`, `ATTN_COMBINE2`, `PREFILL_REUSE2`, `SELECT_TOPK`, `SELECT_FAST`,
    `RESET_DEVICE_ZERO`, `EXPERTS_V2`, `DENSE_DECODE_V2`, `PREFILL_EXPERTS`, `DENSE_RAW`, `QSA_RAW_RING` and
    `PREFILL_SHADOW_PACK`, all =1);
  - `--target-split 23`, context 65536, `--rows 256`.
- Every run checks the kernel log twice. Before it starts, it scans for any xe fault on any card since this lab
  began; after it ends, it scans its own window. Every check was clean.
- No standalone device microbenchmarks were run. New kernels were first tested on the OpenCL CPU device with GPU
  access blocked (`cputest/`, `nodri.so`, DeviceSanitizer).

## Result

**Best exact configuration: `OWNRT_DECODE_NEXT=1`** (dense8 + mix4, default off). Rank 1, split 23, interleaved
final sequence (`runs/F-*`):

| Prompt | Reference 25b3f7542cad (driver median ms) | `OWNRT_DECODE_NEXT=1` | Change |
|---|---|---|---:|
| 4096 rows | 13.415 / 13.415 / 13.428 | 12.969 / 12.979 / 12.991 | **−0.44 ms (−3.3%)** |
| 4096 rows, half_completion median | 13.357 / 13.362 / 13.366 | 12.913 / 12.918 / 12.929 | −0.44 ms |
| 300 rows | 13.254 | 12.807 | −0.45 ms |
| 4096 rows, new binary with the switch off | 13.407 | | default off is inert |

- Every run is bitwise identical to the reference: all 1079 state buffers (`differ_count 0`) and the generated
  tokens.
- No kernel fault in any run (pre and post checks).
- The profile span per half went from 13034 to 12608 µs (`profile-final.json`).
- Rank 0 was not changed here. For two-card service the gain only shows once rank 0's half also drops: it was about
  12.40 ms (11.74 half + 0.66 draft wait), and rank 1 is now about 12.97 ms.

## Profile: rank 1, split 23 (layers 23–47 plus head), 4096-row prompt (`runs/prof-a`, `OWNRT_DECODE_PROFILE=3`)

- Device busy is 12.91 ms per half and the span 13.03 ms.
- Weights read are 3.06 GB per token (gemv sites), which is 5.1 ms at 600 GB/s.
- "Floor @335" is the cold one-launch read rate measured for expert-sized reads (`research/decode-experts`). Large dense
  reads do better, up to 98% of 600 for the head.
- Machine-readable copy: `profile-reference.json`.

| Site | Launches | µs/token | µs/launch | MB/token | Floor @600 GB/s | Floor @335 GB/s | % of 600 floor |
|---|---:|---:|---:|---:|---:|---:|---:|
| `gemv:Q8_0:attention` | 25 | 920 | 36.8 | 417.8 | 696 | 1247 | 76% |
| `gemv:Q6_K:logits` | 1 | 887 | 886.9 | 521.5 | 869 | 1557 | 98% |
| `routed_gemv:IQ4_NL:expsdown` | 23 | 857 | 37.2 | 212.0 | 353 | 633 | 41% |
| `gdn` | 18 | 613 | 34.0 | – | – | – | – |
| `routed_gemv:IQ3_XXS:expsgate` | 9 | 547 | 60.8 | 56.4 | 94 | 168 | 17% |
| `routed_gemv:IQ3_XXS:expsup` | 9 | 523 | 58.1 | 56.4 | 94 | 168 | 18% |
| `gemv:BF16:hc.f.gate` | 25 | 435 | 17.4 | 163.8 | 273 | 489 | 63% |
| `gemv:BF16:hc.f.low` | 25 | 434 | 17.4 | 163.8 | 273 | 489 | 63% |
| `gemv:BF16:hc.a.gate` | 25 | 420 | 16.8 | 163.8 | 273 | 489 | 65% |
| `gemv:BF16:hc.a.low` | 25 | 402 | 16.1 | 163.8 | 273 | 489 | 68% |
| `gemv:Q6_K:gdn.qkv` | 8 | 382 | 47.7 | 172.0 | 287 | 514 | 75% |
| `gemv:Q8_0:shexpdown` | 25 | 374 | 15.0 | 43.5 | 72 | 130 | 19% |
| `gemv:Q5_K:gdn.qkv` | 7 | 354 | 50.5 | 126.2 | 210 | 377 | 60% |
| `hc_mix` | 51 | 334 | 6.5 | – | – | – | – |
| `norm` | 51 | 318 | 6.2 | – | – | – | – |
| `route` | 25 | 308 | 12.3 | – | – | – | – |
| `qsa_attention` | 7 | 298 | 42.5 | – | – | – | – |
| `routed_gemv:IQ3_S:expsgate` | 8 | 291 | 36.4 | 56.3 | 94 | 168 | 32% |
| `gemv:Q6_K:qsa.qgate` | 5 | 278 | 55.7 | 129.0 | 215 | 385 | 77% |
| `routed_gemv:IQ3_S:expsup` | 8 | 277 | 34.6 | 56.3 | 94 | 168 | 34% |
| `hc_combine` | 50 | 247 | 4.9 | – | – | – | – |
| `routed_gemv:IQ2_S:expsgate` | 7 | 229 | 32.7 | 36.7 | 61 | 110 | 27% |
| `gemv:Q6_K:gdn.z` | 8 | 224 | 28.0 | 103.2 | 172 | 308 | 77% |
| `routed_gemv:IQ2_S:expsup` | 7 | 214 | 30.5 | 36.7 | 61 | 110 | 29% |
| `gemv:BF16:router` | 25 | 200 | 8.0 | 65.5 | 109 | 196 | 55% |
| `silu_div4` | 51 | 163 | 3.2 | – | – | – | – |
| `silu_product` | 50 | 139 | 2.8 | – | – | – | – |
| `qsa_select` | 7 | 132 | 18.9 | – | – | – | – |
| `gemv:Q4_K:gdn.z` | 5 | 126 | 25.1 | 44.2 | 74 | 132 | 59% |
| `gemv:Q5_K:qsa.qgate` | 2 | 118 | 59.1 | 43.3 | 72 | 129 | 61% |
| `gdn_norm_gate` | 18 | 111 | 6.2 | – | – | – | – |
| `gemv:IQ4_XS:gdn.qkv` | 2 | 109 | 54.4 | 27.9 | 46 | 83 | 43% |
| `conv` | 18 | 106 | 5.9 | – | – | – | – |
| `moe_combine` | 25 | 104 | 4.2 | – | – | – | – |
| `argmax` | 1 | 102 | 102.1 | – | – | – | – |
| `expert_gather` | 25 | 100 | 4.0 | – | – | – | – |
| `gemv:Q6_K:shexpup` | 8 | 93 | 11.6 | 10.8 | 18 | 32 | 19% |
| `gemv:Q6_K:shexpgate` | 7 | 89 | 12.7 | 9.4 | 16 | 28 | 18% |
| `gemv:Q5_K:gdn.z` | 3 | 85 | 28.4 | 32.4 | 54 | 97 | 64% |
| `gemv:Q6_K:qsa.k` | 7 | 81 | 11.5 | 7.5 | 12 | 22 | 16% |
| `gemv:BF16:gdn.a` | 18 | 74 | 4.1 | 4.4 | 7 | 13 | 10% |
| `gemv:Q6_K:qsa.v` | 7 | 67 | 9.5 | 7.5 | 12 | 22 | 19% |
| `gemv:BF16:qsa.iq` | 7 | 63 | 9.0 | 18.4 | 31 | 55 | 48% |
| `gemv:IQ4_XS:gdn.z` | 2 | 62 | 31.1 | 16.7 | 28 | 50 | 45% |
| `check_status` | 25 | 59 | 2.4 | – | – | – | – |
| `routed_gemv:Q2_0:expsdown` | 2 | 57 | 28.5 | 9.2 | 15 | 28 | 27% |
| `gemv:Q4_K:shexpgate` | 8 | 53 | 6.7 | 7.4 | 12 | 22 | 23% |
| `routed_gemv:IQ4_XS:expsgate` | 1 | 52 | 51.9 | 8.7 | 14 | 26 | 28% |
| `routed_gemv:IQ4_XS:expsup` | 1 | 50 | 49.7 | 8.7 | 14 | 26 | 29% |
| `gemv:IQ4_XS:shexpgate` | 7 | 49 | 7.0 | 6.1 | 10 | 18 | 21% |
| `qsa_prepare` | 7 | 45 | 6.4 | – | – | – | – |
| `gemv:Q4_K:gdn.qkv` | 1 | 44 | 44.5 | 14.7 | 25 | 44 | 55% |
| `gemv:Q5_K:shexpup` | 6 | 42 | 7.1 | 6.8 | 11 | 20 | 26% |
| (8 smaller sites) | 25 | 164 | | | | | |


**Readings.**
- Routed expert gate/up remain the furthest from their floors: IQ3_XXS at 17–18% of 600 GB/s, IQ2_S at 27–29%,
  IQ3_S at 32–34%.
- The shared-expert sites (`shexp*`) and QSA k/v were at 16–19% of 600 before this work.
- The small ops (mix, norm, route, combine, silu, gdn glue, gather, status) add up to about 2.0 ms per half at 2.4–12 µs
  per launch.

## What changed (`decode-next.patch`, switch `OWNRT_DECODE_NEXT`)

**dense8**: the dense decode rows that still went through the local-memory kopt `Multiply`. This covers `gemv()` with
F32 in and out, 32 lanes and no FP32 mirror.
- Q8_0 with K % 64 == 0 (the shared-expert down projection, 2560 × 640): a new `MultiplyQ8Packed<16,1,4>`.
  - Work-item t of a row owns logical lanes 4t..4t+3 of `Multiply`'s mapping, which is Q8_0 block 8i+t.
  - It reads the block's 34 bytes as 9 aligned words with a 2-byte funnel shift by block parity, and converts the
    scale once.
  - Each logical lane keeps `decode8`'s `scale*float(signed8)`, product then add, in chunk order.
  - The tree is `(l0+l1)+(l2+l3)` in registers and then three shuffle levels: the same operands and order as the
    32-lane adjacent-pair tree.
  - `OWNRT_DECODE_NEXT_Q8=0` keeps `Multiply` for Q8_0.
- Q6_K (shared-expert gate/up, QSA k/v): the existing `MultiplyBlockRows<1>`, which decodes from global memory with no
  local staging or barrier. That routed kernel is already exact against `Multiply`.
- Profile: shexpdown 374 → 234 µs; Q6_K shexpgate/up and qsa.k/v about −13 to −18 µs each.
- A/B: −0.25 ms alone.

**mix4**: the HC mix (`native.cpp`, 51 launches per half) with its four `sigmoid(gate)*norm` terms on four adjacent
lanes.
- Lane 4i+h forms term h exactly as the ew path does.
- Lane 4i then computes `sum=0; sum+=t0; sum+=t1; sum+=t2; sum+=t3; out=sum/4`: the same operations in the same order.
  The four exps are no longer serial in one item.
- The guard and position checks match the ew path.
- Profile: hc_mix 334 → 173 µs.
- A/B: −0.14 ms alone; −0.40 to −0.44 ms together with dense8.

New kernel bodies were first tested on the OpenCL CPU device with the GPU blocked (`cputest/`):
- Q8 packed: 0 mismatches and 0 out-of-bounds word reads on real `blk.23.ffn_down_shexp` rows and on synthetic rows
  with negative and subnormal scales, at SG16 and SG32.
- Packed Q6: PASS under DeviceSanitizer. It is exact but slower on the device, so it is a negative result.

Only then did they run on card 27, inside the engine.

## Interleaved end-to-end A/B (driver median ms, two runs each, 4096-row prompt)

Reference (`ref`) is 25b3f7542cad, at 13.41–13.42 in every round. B = dense8 + mix4. All runs: differ_count 0, kfaults 0.

| Round | Arm | Run 1 | Run 2 | vs ref / B | Verdict |
|---|---|---:|---:|---:|---|
| ab2 | ref | 13.421 | 13.414 | | |
| ab2 | dense8 | 13.176 | 13.169 | −0.25 | **kept** |
| ab2 | mix4 | 13.282 | 13.276 | −0.14 | **kept** |
| ab2 | gdn2 (GDN 4 state rows / subgroup) | 13.768 | 13.782 | +0.36 | negative |
| ab2 | gua (IQ3_XXS gate+up+act one launch) | 13.618 | 13.640 | +0.21 | negative |
| ab2 | small (adjacent ew fusions) | 13.414 | 13.408 | 0.00 | neutral, dropped |
| ab2 | comb1 (hc_combine one launch) | 13.459 | 13.469 | +0.05 | negative |
| ab3 | ref | 13.409 | 13.424 | | |
| ab3 | B | 13.002 | 13.032 | −0.40 | **kept** |
| ab3 | xxs2 (IQ3_XXS 2 rows / subgroup, on B) | 13.206 | 13.118 | +0.15 vs B | negative |
| ab3 | xxs8 (IQ3_XXS 8 rows / subgroup, on B) | 13.252 | 13.237 | +0.23 vs B | negative |
| ab3 | kopt2 (Q6 `BlockRows<2>`, on B) | 13.159 | 13.164 | +0.14 vs B | negative |
| ab3 | kopt8 (Q6 `BlockRows<8>`, on B) | 13.402 | 13.396 | +0.38 vs B | negative |
| ab4 | B | 12.980 | 12.996 | | |
| ab4 | norm2 (norm, two-stage, on B) | 12.989 | 12.989 | 0.00 | neutral, dropped |
| ab4 | comb4 (hc_combine four lanes, on B) | 12.983 | 12.968 | −0.01 | neutral, dropped |
| ab5 | B | 12.970 | 12.980 | | |
| ab5 | packed Q6_K SG16 (on B) | 13.226 | 13.237 | +0.26 vs B | negative |
| ab5 | packed Q6_K SG32 (on B) | 13.537 | 13.536 | +0.56 vs B | negative |
| ab6 | IQ4_NL down, default table SG16 (= B) | 12.989 | 12.997 | | |
| ab6 | IQ4_NL variant 0 | 13.172 | 13.150 | +0.17 | negative |
| ab6 | IQ4_NL variant 2 | 13.004 | 13.028 | +0.02 | negative |
| ab6 | IQ4_NL variant 3 | 13.135 | 13.177 | +0.16 | negative |
| ab7 | B | 13.000 | 13.000 | | |
| ab7 | route3 (route, three-stage, on B) | 13.010 | 13.001 | +0.01 | neutral, dropped |

Also negative before the A/B rounds:
- norm1 (single-launch fused norm): profile norm 318 → 1692 µs, and it slowed neighbouring kernels.
- withgnorm, kopt-pair: screened in profile-mode runs only and not promoted.

The code for all of these is in `neg/`.

**IQ3_XXS / IQ3_S / IQ2_S gate+up (the brief's first candidate).** The fused gate+up launch (gua) reads the
activations once and halves the launches. In the profile it went from 1070+139 to 1011+126 µs, but end to end it was
+0.21 ms. Every rows-per-subgroup change was slower too. Those sites stay at 17–34% of the 600 GB/s floor.

In this pipeline their cost is set by the thread count and latency of 10 scattered expert rows, not by the read
rate. The next attempt there must keep the thread count and change only the per-item decode, for example a grid
lookup with fewer ALU ops.

## Lesson: device-profile savings are not end-to-end savings here

`OWNRT_DECODE_PROFILE=3` drains around every site and timestamps each kernel. Several exact changes that are clearly
faster per kernel in that mode are slower in the real pipelined half:

| Change | Profile (µs/token) | End-to-end half |
|---|---:|---:|
| GDN, 4 state rows per subgroup | 613 → 495–539 | **+0.36 ms** |
| IQ3_XXS gate+up+act in one launch | 1070+139 → 1011+126 | **+0.21 ms** |

The changes that won end to end keep or raise the thread count: the packed Q8 lanes, and mix4 at four times the items.
Changes that cut threads (fused launches, more rows per subgroup) lost even where the profile improved.

**Rule for the next lab:** decide by interleaved end-to-end A/B only. Use the profile to find sites, never to accept
levers.

## Exactness

`tp_rank1_driver.py compare` (all 1079 state buffers after 48 decode steps; no buffers ignored):

| Comparison | Compared | differ_count | Only on one side | Other fields |
|---|---:|---:|---:|---|
| F-ref-1 vs F-new-1 (4096) | 1079 | 0 | 0 | none |
| F-ref-2 vs F-new-2 | 1079 | 0 | 0 | none |
| F-ref-3 vs F-new-3 | 1079 | 0 | 0 | none |
| F-ref-p300 vs F-new-p300 (300 rows) | 1079 | 0 | 0 | none |
| F-ref-1 vs F-off-1 (switch off) | 1079 | 0 | 0 | none |
| prof-a vs F-prof (profile mode) | 1079 | 0 | 0 | none |

- The generated token sequences are identical in every pair.
- Every A/B arm in the table above also compared at differ_count 0. That includes the negatives: all variants were
  exact, and they were dropped only for speed.
- Kernel log: 0 fault lines across every run of this lab; no pre-check hit.
- Device work was `tp_rank1_driver` engine-path runs only, on renderD131 (card 27), each checked to hold no other
  render node.

## Files

- `decode-next.patch`: the final change against canonical `engine/src`:
  - `packet6-kopt/kernels.cpp` (dense8);
  - `packet194-expert-diet-engine/native.cpp` (mix4);
  - the new `decode_next.hpp`.
- `neg/`: every measured-negative variant.
  - `lab-all-variants.patch` holds the lab tree with every variant: gua, gdn2, small, comb1, comb4, norm2, erows and
    route3.
  - `negative-withnorm1.patch`, `negative-withgnorm.patch` and `negative-kopt-pair.patch`.
  - `q6_packed.hpp` is the packed Q6_K body.
- `cputest/`: CPU-device bitwise tests of the new Q8_0 and Q6_K kernel bodies on real model rows (PASS, including under
  DeviceSanitizer).
- `scripts/`: run, profile-table and median tools.
- `profile-reference.json`, `profile-final.json` and `results.json`.
