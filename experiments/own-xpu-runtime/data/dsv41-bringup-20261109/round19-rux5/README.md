# rux5: rux4's method on the one-token and check routed-expert kernels (2026-11-13, card 2)

Status: done (started 2026-11-13 01:45); patch `rux5-1.patch`, switch `OWN_RUX5` (default 0). Work tree `b/` (lab HEAD 2b3f66a26 engine copy + `kernels/sycl_v41_routed_rux5.hpp`
+ the `OWN_RUX5` plumbing), bench `b/tools/bench/bench_rux5.cpp` (+ `bench_rux5_head.inc`), machine code in `isa/<build>/`,
runs in `out/`, tools in `tools/` (`isa5.py`: register mode, spills, SLM / global load round trips per loop pass;
`gain5.py`: per-format table and per-step / per-check prediction; `plumb5.py`, `mkpatch5.sh`, `syncheck5.sh`).

## 1. Machine code first (before any variant): is rux4's serialized-gather pattern there?

Tool: `tools/isa5.py` (rux4's isa4.py extended): in the hottest loop, every wait on a load's token is a "round trip";
a trip's size = loads issued since the previous wait of that kind, cover = instructions between the trip's last load
and the wait. rux4's pattern = SLM trips of 1 gather with cover 0-2.

Dumps read before building (closest to today's code: xperm `isa/xdq4` one-token forms, `isa/led1` IQ2_S Pe at 128,
`isa/l34-p1/p5` and rux4 `isa/p10` RoutedU3):

One-token kernels (M = 1, slot-major P forms, row whole in one sub-group, fully unrolled per segment):

| kernel (today) | regs | SLM gathers / loop pass | SLM trips (gathers each) | trips of 1 gather | cover (median) |
|---|---|---|---|---|---|
| IQ2_S gate+up RoutedIQ2SPe128<20> | 128 | 192 | 98 (2.0) | 63, cover <= 2 for 56 | 2 |
| IQ2_XXS gate+up RoutedIQ2XXSPe<20> | 128 | 64 | 13 (4.9) | 3 | 15 |
| IQ1_S gate+up RoutedIQ1SPb<20> | 128 | 160 | 74 (2.2) | 49 | 17 |
| IQ3_XXS down RoutedIQ3XXSPb<9> | 128 | 72 | 36 (2.0) | 26 | 18 |
| IQ2_S down RoutedIQ2SPd<9> | 128 | 144 | 44 (3.3) | 3 | 7 |
| IQ2_XS down RoutedIQ2XSPb<9> | 128 | 72 | 37 (1.9) | 28 | 19 |
| IQ2_XXS down RoutedIQ2XXSPd<9> | 128 | 144 | 46 (3.1) | 11 | 20 |

Reading: no spills; the compiler already groups the one-token gathers 2-5 per trip with 7-20 instructions of cover,
except IQ2_S gate+up at 128 registers, where the compile-time tail segment of each row pair (one of 5 segments)
runs ~60 gathers one by one (cover 0-2): rux4's pattern, on ~1/5 of that kernel's gathers. The global loads (row
words, x blocks) wait with 25-70 instructions of cover.

Checks (M = 2-6, RoutedU3<RU3*, 6> single rows, 128 registers, no spills): SLM gathers already 8 per trip (cover
7-24): no serialized gathers. But every x block read (sg_bloadN<8>, 4 messages) is waited on 3 instructions later:
IQ2_S<20> 77 x trips per loop pass (cover 3), IQ1_S<20> 77, IQ3_XXS<9> 32, IQ2_S<9> 57, IQ2_XXS / IQ2_XS single-row
forms 27 / 57 (cover 3). At 2-6 tokens most groups have one slot, so each 8-value sub-block of a row waits once for
its x block right before the products (rux4's second bullet, "each slot waits for its x block").

Prediction (before building):
- one-token: the gather lever is small. IQ2_S gate+up: its serialized tail segment ~1/5 of the gathers -> -2..-5 %;
  the other six formats ~0 from gathers alone. Anything larger has to come from the schedule (rows per tile, register
  mode, 64 work-groups) - unknown, measure.
- checks: no gather lever; the x-read lever is the xperm ledger's "x exposed" share (IQ2_S gate+up: 6.6 of 46.8 us at
  2 tokens, 23.4 of 102 at 5): issuing slot 0's x read before the decode (XA 1/2) and slot i + 1's before slot i's
  products, if it stays in 128 registers at one row per sub-group, removes half to most of it: -7..-14 % per launch
  at 2 tokens, -10..-20 % at 5.

## 2. Forms (RoutedUQ, `kernels/sycl_v41_routed_rux5.hpp`)

rux4's RoutedUP (gathers of a sub-block first, phase A; their finish, phase B) with PF 0, plus:
- IDS (one-token): the P forms' slot ids instead of expert groups (group u = slot u, one slot, MT 1), so the one-token
  launch needs no grouping kernel; same rows, x and outputs as the P forms.
- tiles of R rows whenever rows % R == 0 (no block-size threshold).
- XA 3 (MT 1): the next sub-block's x read during this sub-block.
Bit-identity: each accumulator gets the same mul and add on the same values in the same (block, element) order as
the P forms and RoutedU3; only updates of different accumulators interleave; R2_XSUM as both.

## 3. What the bench says (card 2, real weights of all 384 experts, real 3K-prompt picks, every output float compared)

Bench `bench_rux5` (rux4's scaffolding): per format the card-2 rows (gate + up 2 x 384 rows at 5,120 columns, down
864 rows at 13,824), the ids of real tokens from `runs/u84/p3k-ids-per-layer.txt` (16 sets at M = 1, 8 per check
size), checks grouped as the engine's ExpertGroupM does (cap 6). Today's kernels: one-token RoutedIQ2SPe128 (IQ2_S
gate + up) / RoutedIQ*Px (the rest), checks RoutedU3<RU3*, 6> without pair code (= OWN_U3_NOPAIR's). Timing "cold"
(the default, matches the engine per the xperm ledger: 48 MB streamed and x / ids touched before each launch) and
"warm" (COLD=0). Every run: every candidate's outputs bitwise against today's on every set.

Queue 1 (one run each, 7 + 5 forms) and queue 2 (three cold runs of 6 rounds + one warm, 9 + 8 forms):
- Checks (M = 2-6): the gathers-first form at one row per sub-group wins everywhere, -7 to -16 % per launch.
  Best: MT = M (the kernel compiled for the check's own token count, so the per-slot loop is not unrolled to 6) with
  slot 0's x read after the gathers (XA 1); XA 2 (before the gathers) and LV 1 are within 0.5 %. At M = 6 MT 6 with
  x right before the products (XA 0) is best: the XA 1 form at MT 6 spills 128 B (IQ2_S) and loses 1-2 %.
  Lost: 2-row tiles (spill from M 3 on, up to +268 %), E 4 (+2 to +11 % from M 3), 256 registers at 64 work-groups
  (+1 to +26 %).
- One token (M = 1): small. Best R 1 with x before the gathers (XA 2): IQ2_S gate + up -5.0 %, IQ1_S -6.1 %,
  IQ3_XXS down -4.9 %; IQ2_S down R 1 E 4 -3.4 %; IQ2_XS down -2.5 %; IQ2_XXS gate + up 2-row tiles -1.4 %; IQ2_XXS
  down: every form slower (+2.7 % best), today's kernel stays. Lost: 3-row tiles (+5 to +28 %, spills or serial
  gathers), 4-row tiles at 256 registers / 64 WGs (+3 to +16 %), the next sub-block's x ahead (XA 3, -2 % at best).
- The machine-code prediction held for one token (gather lever small) and was too low for checks: the x-read lever
  was predicted at -7..-14 %, the measured -11..-13 % also includes MT = M (shorter unrolled slot code).

## 4. Picks (`Rux5Pick1` / `Rux5PickK` in `kernels/sycl_v41_routed_rux5.hpp`, `logs/picks-v3.txt`)

Checks: one rule for all seven card-2 shapes (within 0.7 % of each shape's own best, fewer instantiations):
`RoutedUQ<RU3*, MT = M, R 1, E 8, XA 1, LV 0, 128 registers>` at M = 2-5, `RoutedUQ<RU3*, 6, R 1, E 8, XA 0>` at M = 6.
One token (`RoutedUQ<RU3*, 1, R, E, XA, LV, 128, 0, IDS>` on the slot ids):

| shape | form |
|---|---|
| IQ2_S gate + up (20 blocks) | R 1, E 8, XA 2 |
| IQ2_XXS gate + up | R 2, E 8, XA 2 |
| IQ1_S gate + up | R 1, E 8, XA 2 |
| IQ3_XXS down (9 blocks) | R 1, E 8, XA 2 |
| IQ2_S down | R 1, E 4, XA 1 |
| IQ2_XS down | R 1, E 8, XA 1, LV 1 |
| IQ2_XXS down | today's RoutedIQ2XXSPx (no pick) |

Shapes not on card 2's list (IQ3_XXS / IQ2_XS gate + up, IQ1_S down) have no pick: today's kernels.
All picks: 128 registers, no spill (machine code `isa/p2*`), the backend's 128 work-groups.

## 5. Confirmation: the picks as the backend instantiates them (bench_rux5_c4: `-DRUX5_C1=VarP -DRUX5_CK=VarP`)

Five cold runs (8 rounds each; the first compares every output float of every set) and two warm runs, 2026-11-13
02:59-03:04, card 2 (`out/run-c4-*.txt`). Cell: today's us per launch -> the pick's (change).
Cold (engine-like: 48 MB streamed and x / ids touched before each launch), us per launch (5 runs)

| format | M = 1 | M = 2 | M = 3 | M = 4 | M = 5 | M = 6 |
|---|---|---|---|---|---|---|
| IQ2_S gate+up (15x) | 29.1 -> 28.4 (-2.4 %) | 46.7 -> 41.0 (-12.2 %) | 58.1 -> 50.5 (-13.1 %) | 71.5 -> 62.1 (-13.2 %) | 88.5 -> 75.0 (-15.2 %) | 107.0 -> 93.7 (-12.4 %) |
| IQ2_XXS gate+up (15x) | 23.8 -> 23.6 (-1.1 %) | 41.3 -> 36.4 (-11.9 %) | 51.9 -> 45.5 (-12.2 %) | 63.2 -> 55.7 (-11.9 %) | 77.9 -> 67.5 (-13.3 %) | 95.5 -> 83.3 (-12.7 %) |
| IQ1_S gate+up (10x) | 25.5 -> 24.8 (-2.9 %) | 40.7 -> 36.8 (-9.7 %) | 51.6 -> 44.9 (-13.0 %) | 64.0 -> 55.5 (-13.3 %) | 79.2 -> 70.6 (-10.9 %) | 94.3 -> 82.4 (-12.7 %) |
| IQ3_XXS down (15x) | 20.4 -> 19.3 (-5.3 %) | 32.8 -> 29.4 (-10.2 %) | 39.7 -> 35.3 (-11.0 %) | 46.9 -> 42.2 (-10.0 %) | 55.4 -> 50.3 (-9.3 %) | 65.9 -> 59.5 (-9.7 %) |
| IQ2_S down (15x) | 18.6 -> 17.7 (-4.6 %) | 28.9 -> 26.6 (-8.2 %) | 35.1 -> 32.1 (-8.5 %) | 41.5 -> 37.5 (-9.7 %) | 49.3 -> 44.2 (-10.4 %) | 58.9 -> 53.4 (-9.3 %) |
| IQ2_XS down (6x) | 17.2 -> 16.6 (-3.5 %) | 27.9 -> 25.2 (-9.7 %) | 34.0 -> 30.6 (-9.8 %) | 40.3 -> 35.8 (-11.1 %) | 47.9 -> 42.2 (-11.9 %) | 56.6 -> 50.7 (-10.5 %) |
| IQ2_XXS down (3x) | 15.9 (today) | 27.6 -> 24.5 (-11.2 %) | 33.8 -> 30.2 (-10.6 %) | 40.3 -> 35.6 (-11.6 %) | 47.9 -> 41.9 (-12.5 %) | 56.1 -> 49.6 (-11.6 %) |

bitwise PASS (format, M) cells: 42 of 42

- card 2 routed kernels per one-token step: 1.785 -> 1.731 ms (-0.054 ms, -3.0 %)
- card 2 routed kernels per check of 2 tokens: 2.903 -> 2.593 ms (-0.311 ms, -10.7 %)
- card 2 routed kernels per check of 3 tokens: 3.594 -> 3.176 ms (-0.418 ms, -11.6 %)
- card 2 routed kernels per check of 4 tokens: 4.350 -> 3.839 ms (-0.510 ms, -11.7 %)
- card 2 routed kernels per check of 5 tokens: 5.292 -> 4.641 ms (-0.651 ms, -12.3 %)
- card 2 routed kernels per check of 6 tokens: 6.360 -> 5.626 ms (-0.733 ms, -11.5 %)
- per extra check token (M 2 -> 5): 0.796 -> 0.683 ms
- over the tl105 mix of steps (M 1-6: 32/30/20/6/8/4 per 100): -0.306 ms per step on average (-0.425 ms per check of 2-6 tokens)

Warm (same launch repeated), us per launch (2 runs)

| format | M = 1 | M = 2 | M = 3 | M = 4 | M = 5 | M = 6 |
|---|---|---|---|---|---|---|
| IQ2_S gate+up (15x) | 26.4 -> 24.6 (-6.8 %) | 45.7 -> 39.1 (-14.5 %) | 58.9 -> 50.0 (-15.1 %) | 76.3 -> 64.9 (-15.0 %) | 97.1 -> 81.0 (-16.6 %) | 118.1 -> 102.1 (-13.6 %) |
| IQ2_XXS gate+up (15x) | 20.9 -> 20.8 (-0.2 %) | 41.3 -> 34.8 (-15.8 %) | 53.1 -> 45.3 (-14.7 %) | 66.7 -> 57.2 (-14.2 %) | 85.3 -> 72.5 (-15.0 %) | 105.4 -> 90.2 (-14.4 %) |
| IQ1_S gate+up (10x) | 22.0 -> 20.4 (-7.2 %) | 39.4 -> 34.0 (-13.6 %) | 52.2 -> 43.9 (-15.8 %) | 67.4 -> 57.2 (-15.1 %) | 86.7 -> 76.2 (-12.1 %) | 104.7 -> 89.6 (-14.4 %) |
| IQ3_XXS down (15x) | 17.6 -> 16.6 (-5.9 %) | 31.5 -> 27.3 (-13.6 %) | 39.3 -> 33.8 (-13.9 %) | 47.9 -> 42.3 (-11.7 %) | 60.9 -> 54.3 (-10.7 %) | 71.1 -> 62.8 (-11.6 %) |
| IQ2_S down (15x) | 14.9 -> 13.7 (-8.0 %) | 26.1 -> 23.0 (-11.7 %) | 32.7 -> 28.6 (-12.4 %) | 41.8 -> 36.7 (-12.4 %) | 52.3 -> 46.1 (-11.9 %) | 67.5 -> 60.1 (-11.0 %) |
| IQ2_XS down (6x) | 13.7 -> 12.5 (-8.6 %) | 25.1 -> 21.6 (-14.1 %) | 32.3 -> 27.6 (-14.8 %) | 39.8 -> 33.7 (-15.4 %) | 49.0 -> 41.7 (-14.9 %) | 62.0 -> 53.6 (-13.5 %) |
| IQ2_XXS down (3x) | 11.1 (today) | 24.7 -> 20.8 (-15.9 %) | 31.4 -> 26.9 (-14.4 %) | 39.5 -> 33.8 (-14.6 %) | 48.7 -> 41.4 (-15.0 %) | 59.1 -> 50.6 (-14.5 %) |

bitwise PASS (format, M) cells: 0 of 42 (runs without the check)

- card 2 routed kernels per one-token step: 1.533 -> 1.449 ms (-0.084 ms, -5.5 %)
- card 2 routed kernels per check of 2 tokens: 2.788 -> 2.394 ms (-0.394 ms, -14.1 %)
- card 2 routed kernels per check of 3 tokens: 3.569 -> 3.052 ms (-0.517 ms, -14.5 %)
- card 2 routed kernels per check of 4 tokens: 4.523 -> 3.890 ms (-0.632 ms, -14.0 %)
- card 2 routed kernels per check of 5 tokens: 5.740 -> 4.944 ms (-0.796 ms, -13.9 %)
- card 2 routed kernels per check of 6 tokens: 7.029 -> 6.098 ms (-0.931 ms, -13.2 %)
- per extra check token (M 2 -> 5): 0.984 -> 0.850 ms
- over the tl105 mix of steps (M 1-6: 32/30/20/6/8/4 per 100): -0.387 ms per step on average (-0.530 ms per check of 2-6 tokens)

Bitwise over all runs of this study (queues 1, 2 and c4; every run with the check): 168 (shape, M) cells, 861
kernel-vs-today comparisons, 120,545,280 output floats, 0 differences. Every run's kernel journal clean.

## 6. Patch and integration

- `rux5-1.patch` (against lab HEAD 71cb3cc08 = tp109 sources; `git apply --check` OK; engine syntax check OK): new
  `src/stage2/packet3/kernels/sycl_v41_routed_rux5.hpp` (RoutedUQ + picks), bench `tools/bench/bench_rux5.cpp` +
  `bench_rux5_head.inc`, and the plumbing (`tools/plumb5.py`): `backend_sycl_v41.hpp` includes the header;
  `routed_pair` (one-token gate + up, no extra rows) and `routed_gemv` (one-token downs) take the Rux5Q1 form when
  `rux5` is set and the shape has a pick; `routed_m` (backend_sycl_v41_mt.inc) takes Rux5QK<.., M> for blocks of 2-6
  tokens (cap <= 6, below OWN_MT_RUX_MIN) before the OWN_U3_NOPAIR / RoutedU3 path; `bool rux5 = false;` and
  `OWN_RUX5` in own_run_v41.cpp. OWN_RUX5=0 (default): no launch changes, only extra template code compiled in.
- Env: `OWN_RUX5=1`. It acts only on the default one-token paths (OWN_FIN_MOVE=0, OWN_DOWN_EX=0, OWN_EXP_PAIR=1:
  the extra-row launches keep today's kernels) and on expert-major blocks of 2-6 tokens (OWN_MT_EU): the checks,
  and also prompt blocks of 2-6 tokens if OWN_PROMPT_BLOCK is set that small (same bits there too).
- New instantiations (engine): one-token 6 RoutedUQ kernels (one per picked shape); checks 7 shapes x 5 sizes = 35
  RoutedUQ kernels (MT 2, 3, 4, 5 and 6). All 128 registers (K::GRF = 128 pinned; WGCAP 0 = the backend's 128).
- Assumption used by MT = M: a token's 6 experts are different, so an expert group of an M-token block holds at most
  M slots (checked on all 132,920 token-layer pairs of the u84 dump: no repeat; RouteP takes the 6 best ranks, distinct
  experts; only NaN router scores, already broken output, could leave a rank untaken).
- Bit-identity argument: section 2; measured: section 5.

## 7. Predicted gain (card 2, the critical card; the same shapes run on every card)

From the cold confirmation (engine-like) and tl105's step times (card 2 busy per step: 8.82 ms at one token, 11.83 /
13.79 / 15.25 / 17.45 / 18.77 ms per check of 2 / 3 / 4 / 5 / 6 tokens):

| step | routed kernels today -> rux5 | change | share of the step |
|---|---|---|---|
| one token | 1.785 -> 1.731 ms | -0.05 ms | -0.6 % |
| check of 2 tokens | 2.903 -> 2.593 ms | -0.31 ms | -2.6 % |
| check of 3 tokens | 3.594 -> 3.176 ms | -0.42 ms | -3.0 % |
| check of 4 tokens | 4.350 -> 3.839 ms | -0.51 ms | -3.3 % |
| check of 5 tokens | 5.292 -> 4.641 ms | -0.65 ms | -3.7 % |
| check of 6 tokens | 6.360 -> 5.626 ms | -0.73 ms | -3.9 % |

Per extra check token the routed kernels cost 0.80 -> 0.68 ms. Over tl105's mix (per 100 steps 32 one-token, 30 / 20
/ 6 / 8 / 4 checks of 2-6 tokens) -0.31 ms per step on average (-0.42 per check). Warm the gains are larger (one token
-0.08 ms, checks -0.39 to -0.93 ms). Not measured here: the engine itself (the coordinator's gate), other cards.

## 8. Files and how to reproduce

- `rux5-1.patch`: `bash tools/mkpatch5.sh [BASE]` (fresh archive of BASE, `tools/plumb5.py`, the header + bench
  from `b/`, then `git apply --check`); engine syntax check `bash tools/syncheck5.sh` (logs/syncheck.log: HEAD
  71cb3cc08 + patch, exit 0).
- Picks: `python3 -I tools/setpicks5.py $(cat logs/picks-v3.txt)` (header copy `hdr/picks-v3.hpp`).
- Bench: `./build.sh TAG FMT_MASK [DUMP] "-DRUX5_C1=VarQ<..>, .." "-DRUX5_CK=.."` (or `VarP` = the picks), run
  `./run.sh TAG bench_rux5_TAG [ROUNDS=n] [COLD=0] [NOCHECK=1] [MS=..] [ONLY=..]`; queues `queue1.sh` - `queue4.sh`.
- Analysis: `python3 -I tools/gain5.py out/run-*.txt [--all] [--picks 0.01]`, `python3 -I tools/table5.py COLD.. --warm WARM..`,
  machine code `python3 -I tools/isa5.py isa/<build> RoutedUQ`.
