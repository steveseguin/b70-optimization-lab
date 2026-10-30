# Multi-row verify kernels, K1–K3 (2026-10-30)

The goal was a whole-pass M-row ratio low enough that deeper speculation beats today's one-guess pipeline, with every
row bit-identical to one-row decode. **The campaign stopped at the K3 gate.** Every path built here is exact. The pass is
still too slow: 1.42–1.47× at two rows (gate ≤ 1.35×) and 2.32–2.46× at four rows (gate ≤ 1.9×). K4, the verifier, was
not started.

## In plain words

- **K1: the dense projections now cost about one row's time for two rows.** New small-row tiles cover T = exactly M token
  rows with 1–2 weight rows per subgroup. For the Q4_K/Q5_K/IQ4_XS blocks they use the one-row kernel's header-word
  decode. At M = 2 they bring:
  - attention output to 1.02–1.03× of one row;
  - GDN qkv to 1.12–1.15×, GDN z to 1.15–1.16× and QSA q/gate to 1.06–1.10×;
  - the hyper-connection BF16 projections to 0.92–1.04× and the router to 0.96×.

  At M = 3 and 4 these sites cost 1.01–1.30× and 1.08–1.38×. The shared expert is the exception (below).
- **The shared expert does not reach the target and is closed.** At M = 2 it costs 1.5–1.75×. These are tiny matrices
  (640 × 2560 and 2560 × 640) that take 7–9 µs at one row. They are limited by launch time and by too few row subgroups.
  Going lower would need a split-K, which changes the add order, or fusing the three kernels into one.
- **K2: routed experts that share an expert across rows were built three times, and every version was slower.** Each
  version is bitwise identical to the one-row kernels: 45/45 CPU cases, plus both ranks on the card. Each was still
  slower than simply running every slot with the one-row kernel. At M = 2 on rank 0 the per-slot kernels take 4.58 ms.
  The three grouped versions took 7.76, 8.39 and 9.41 ms. The ideal from the distinct-expert count would be 3.95 ms.
  This is the main open problem.
- **K3: the best exact combination misses the gate.** That combination is the K1 tiles, per-slot experts and the existing
  multi-row `moe_combine`. Full state dumps and every output row match one-row decode on both ranks. The whole pass,
  rank 0 / rank 1 (device span over the one-row pass without the head):

| rows M | rank 0 | rank 1 | gate | census projection (best existing tiles / ideal #1) |
| ---: | ---: | ---: | ---: | --- |
| 2 | **1.42×** | **1.47×** | ≤ 1.35× | 1.55× / 1.17× |
| 3 | 1.78× | 1.83× | | 1.82× / 1.35× |
| 4 | **2.32×** | **2.46×** | ≤ 1.9× | 2.18× / 1.50× |

  What is left over at M = 2 is the experts (4.6 / 5.3 ms, 2× the one-row cost) and the shared expert. At M = 4 the IQ4_NL
  down projection also falls off its fast kernel: 40 slots exceed the packed kernel's 32-slot cap. Raising the cap is exact
  and trivial, but on its own it would only reach about 2.15×.
- **What it would take to pass:** experts close to the distinct-expert ideal, plus either a fused shared expert or
  accepting its 1.5×. With the K1 tiles and ideal experts, the sums give 1.34× (M = 2) and 1.8× (M = 4). That passes, but
  only just.

## Exactness

- **CPU first.** The OpenCL CPU device runs with the GPU blocked by `cputest/nodri.so`.
  - Tiles: [test_reuse2_small.cpp](cputest/test_reuse2_small.cpp), 840 + 900 cases, all bitwise. It covers every
    small-row tile × every dense format (including the new `BlockV2`) × 1, 2, 3, 4 and 13 token rows, against host
    replicas of the one-row per-lane sequences. The production tiles were rechecked after the T = 3 padding change.
  - Grouped experts: [test_grouped.cpp](cputest/test_grouped.cpp), 45/45 cases for each attempt. The references are
    `dn2::xxs_packed<4>` itself and a verbatim replica of `kopt::MultiplyBlockRows<4>`, run on real expert rows from the
    GGUF. The route sets are M = 2, 3, 4 × overlapping experts, invalid and short routes, and a 6-slot crowd on one
    expert.
- **On the card,** rank harness, one card per rank. Every run compared all output rows of the 2, 3 and 4-row chunks
  against one-row decode, and the final full state dump against the census runs C0/C1 ([compare_state.py](compare_state.py)).
  - Rank 1: 1,079 buffers; rank 0: 1,029; plus rank 1's 144 tokens (= suite oracle) and rank 0's 144 draft guesses.
  - Runs: K1 rounds 1 and 2 with every tile cycled per chunk, K2 attempts 1–3, and K3.
  - All gates in `results/*-gate-*.json` passed.
- No device incident in 16 arms; kernel-log checks are clean (`logs/kernel-log-*`).

## K1: small-row token tiles (default off)

- `OWNRT_PREFILL_REUSE2_SMALL=1` selects, for chunks of 2–4 token rows, a tile from `REUSE2_SMALL_CONFIGS`:
  RW 1/2/2/4 × T = M, at GRF 128/128/256/256.
  - `OWNRT_PREFILL_REUSE2_SMALL_<BLOCK|P33|KOPT|BF16>` takes one index, or a list for M = 2, 3, 4.
  - `OWNRT_PREFILL_REUSE2_SMALL_CYCLE=1` is a diagnostic that cycles the choice per chunk.
- `reuse2::Tile` pads a T that is not a power of two (T = 3) in the reduction only. Power-of-two tiles are unchanged.
- `reuse2::BlockV2<T>` is the dense-block decode with `gsqn::v2::rows_fast`'s header loads and `iq4_level`. The old
  `Block32` indexes a private level table, and its IQ4_XS sites cost 2.1–2.9×.
- Measured choice used in K3: `BLOCK=0` (RW1), `P33=2` (RW2/GRF256), `BF16=0,2,2`, `KOPT=1`.
- Round 1 also tried RW 2/4/8 at GRF 128/256. RW 4 at GRF 128 is 3–4× (spills), and RW 8 lost everywhere.

Best tile per site, ratio to the one-row decode time (rank 0 / rank 1; [k2-rank*-small-tiles.json](results/)):

| site | M = 2 | M = 3 | M = 4 |
| --- | --- | --- | --- |
| attention (Q8_0) | 1.03 / 1.02 | 1.07 / 1.07 | 1.08 / 1.08 |
| gdn.qkv (Q6_K, Q4_K, Q5_K, IQ4_XS by layer) | 1.12 / 1.15 | 1.28 / 1.27 | 1.36 / 1.37 |
| gdn.z | 1.16 / 1.15 | 1.30 / 1.30 | 1.38 / 1.38 |
| qsa.qgate | 1.06 / 1.10 | 1.21 / 1.27 | 1.28 / 1.34 |
| hc.a/f.gate (BF16 320 → 10240) | 0.93–0.95 / 0.92–0.93 | 1.03–1.04 / 1.01–1.02 | 1.11 / 1.10–1.11 |
| hc.a/f.low (BF16 10240 → 320) | 0.99–1.04 / 1.00–1.02 | 1.11–1.17 / 1.13–1.14 | 1.21–1.24 / 1.23–1.24 |
| router (BF16) | 0.96 / 0.96 | 1.03 / 1.01 | 1.03 / 1.03 |
| shexp gate / up / down | 1.68 / 1.55 / 1.51 (rank 0) | 2.05 / 1.68 / 1.63 | 2.36 / 1.80 / 1.67 |

## K2: grouped routed experts (default off, `OWNRT_EXPERTS_GROUPED=1`)

`stage2/packet194-expert-diet-engine/expert_groups.hpp` groups the chunk's 10·M slots by expert, with at most 4
members. Each member keeps the one-row kernel's values, order and tree. Coverage:
- IQ3_XXS (`xxs_grouped`, from `dn2::xxs_packed`);
- IQ2_S and IQ3_S (`rows_grouped`, from `MultiplyBlockRows`);
- IQ4_NL (`iq4nl_grouped`, from `MultiplyIQ4NLPacked`).

Q2_0 and IQ4_XS keep the per-slot kernels.

Summed time of gate + up + down per pass, rank 0 / rank 1:

| rows M | per-slot one-row kernels | attempt 1 | attempt 2 | attempt 3 | ideal by distinct experts |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 4.58 / 5.28 ms | 7.76 / 8.84 | 8.39 / 9.30 | 9.41 / 10.68 | 3.95 / 4.31 |
| 3 | 6.54 / 7.52 | 11.01 / 12.29 | 11.54 / 12.64 | 14.52 / 16.38 | 5.44 / 5.74 |
| 4 | 10.88 / 12.93 | 16.80 / 19.20 | 15.29 / 16.68 | 21.00 / 23.84 | 6.69 / 6.88 |

How the three attempts differ:
- **Attempt 1:** each subgroup finds its own group with O(n) dependent route loads per lane, on a worst-case grid.
- **Attempt 2:** the grouping is built once per subgroup by shuffles, and each subgroup loops over every G-th group.
  That leaves too few, too-long subgroups.
- **Attempt 3:** the shuffle table with one group per subgroup.

None of them is a register-spill problem: an AOT compile reports only about 2 spilled registers, in `xxs_grouped`.

The fact that attempt 3 is slower than per-slot, even with one group per subgroup, points at the grouped body itself. The
suspects are the per-member predicated loads and stores, the lambda/loop structure, or lost load scheduling. It does not
point at the grouping. The next step, if reopened, is a standalone device microbench of one site: `xxs_packed` per slot
against `xxs_grouped` at n = 20, plus variants with the member loop removed. Then build only what that shows.

## K3: the best exact combination, measured

Environment, on top of the r7 launch:
- `OWNRT_PREFILL_REUSE2_SMALL=1` with the K1 choices above;
- `OWNRT_PREFILL_EXPERTS_IQ3=2`, `_ELEM=2`, `_KOPT=2` (per-slot one-row expert kernels instead of the 256-row grouped
  prefill kernels);
- `OWNRT_PREFILL_MOE_NATIVE=1`.

Binary `044e0a54cef8`; runs K5r0 and K5r1 ([k3c-rank*-passratio.json](results/), [k3c-gate-*](results/)).

| rows M | rank 0 chunk (ms) | ratio | rank 1 chunk (ms) | ratio |
| ---: | ---: | ---: | ---: | ---: |
| 1 (decode half, head excluded on rank 1) | 10.12 | 1 | 10.88 | 1 |
| 2 | 14.38 | 1.42 | 15.95 | 1.47 |
| 3 | 18.00 | 1.78 | 19.94 | 1.83 |
| 4 | 23.44 | 2.32 | 26.72 | 2.46 |

The default batched path costs 2.75× at M = 2 (census), so the existing kernels with tile choices are 1.9× better at
two rows. The verifier go/no-go is **no-go** on these kernels.

## Files

- Engine (default-off flags): `prefill_reuse2.hpp` (T padding, `BlockV2`), `prefill_reuse2_op.hpp` (small list and
  selection), the reuse2 hooks in `block.hpp`, `p33_submit.cpp` and `kopt/kernels.cpp`, `expert_groups.hpp`, the grouped
  dispatch in `expert-iq3xxs-block/.../block.hpp` and `kopt/kernels.cpp`, and the prefill bypass in `prefill_engine.hpp`.
  Receipts: `ab62735bca3c` (K1 r1), `7c33443497cf` (K1 r2 + K2 a1), `e7b59001d263` (K2 a2), `044e0a54cef8` (K2 a3; K3).
- Harness: [mr_driver.py](mr_driver.py) and [run_mr.sh](run_mr.sh) (copies of the census driver with `--env`),
  [small_tiles.py](small_tiles.py), [passratio.py](passratio.py), [compare_state.py](compare_state.py), [analyze.py](analyze.py).
- Raw runs (traces, dumps, rows): `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/multirow-k{1,2,3,3b,3c}-runs`
  (sha256 lists beside them).
