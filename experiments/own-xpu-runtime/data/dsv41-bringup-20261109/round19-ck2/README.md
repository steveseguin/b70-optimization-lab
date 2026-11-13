# ck2: cheaper dense rows at 2-3 token checks (DeepSeek V4.1, card share, card 3)

2026-11-12, helper ck2. One card (level_zero:3), bitwise against the engine's current launches on real GGUF rows.
Engine tree: tp105 (HEAD 2613d1aa3). Nothing in the engine tree is edited; the patch is opt-in (`OWN_CK2`).

## 1. Where the 1.4 ms "dense" jump at M=2 really comes from (tl105, card 2)

The brief's table (dense rows 3.26 / 4.65 / 5.21 ms at M = 1 / 2 / 3) compares different launch sets. At M >= 2 the
"dense" kernel families also hold work that runs elsewhere at M = 1:

| moved into the M >= 2 "dense" families | M=2 us/check | where it runs at M=1 |
|---|---|---|
| router + the FFN mix's dot rows (DenseRowsG<GemvH16P> + HcDotsRows riders) | 615 | FlNormK (fl-1, one launch) |
| shared down (Q8 / Q5) | 270 | FlDownComb (with the comb) |
| other H16 rows | 97 | RoutePRows etc. |

Per role (`tools/roles_by_m.py`, `roles-card2.txt`, card 2, us per check; per launch in brackets):

| role | M=1 | M=2 | M=3 |
|---|---|---|---|
| FFN pre-norm + mix dots + router (40 layers) | 541 (13.5) | 615 + 133 SkNormWM = 748 (18.7) | 853 + 136 = 989 (24.7) |
| q_a + kv (+ attention dots riding) Q8 | 468 + 76 (19.5) | 662 (24.5) | 721 (26.7) |
| q_a + kv (+ dots) Q6 | 225 (17.3) | 326 (25.1) | 378 (29.1) |
| o_b Q8 | 423 (15.7) | 465 (17.2) | 556 (20.6) |
| o_b Q6 | 190 (14.6) | 242 (18.6) | 290 (22.3) |
| q_b Q8 | 633 (23.5) | 629 (23.3) | 658 (24.4) |
| q_b Q6 | 274 (21.1) | 308 (23.7) | 340 (26.1) |
| o_a Q8 | 492 (18.2) | 492 (18.2) | 514 (19.0) |
| o_a Q6 | 256 (19.7) | 211 (16.2) | 224 (17.2) |

Real excess per check over M=1, card 2: M=2 about +460 us (FFN norm+dots+router +208, attention norm+dots+q_a/kv
+105, o_b +92, q_b Q6 +34, HcPostPre +25, rest ~+40, o_a Q6 -45); M=3 about +1.0 ms (FFN +448, attention +220,
o_b +232, q_b Q6 +65, rest ~+70). Card 0 shows the same pattern (`roles-card0.txt`).

## 2. Instructions per weight and ALU headroom (ISA census, `isa/isa1`, `src/ck2_isa_tu.cpp`)

SIMD32 instructions per weight (per weight-token for T > 1), 128-register mode, no spills:

| form | fp32 mul/add | convert / strided mov | int / addr | total | note |
|---|---|---|---|---|---|
| one-token Q8_0 GemvQ8P | 3.0 | ~3.2 | ~1.8 | ~9.4 | o_b at M=1 ~43 % ALU-busy |
| WS T2 Q8_0 (q_b, o_a picks) | 2.0 | ~2.6 | ~1.7 | ~6.3 per weight-token | same time as M=1 |
| WS T1R1 Q8_0 (o_b at M=2) | | | | ~9.4 per weight-token | ~13.9 us ALU of 17.2 measured: near ALU-bound |
| Q6_K forms | | | | ~13.6 | |
| H16 router (GemvH16P<160>), estimate | 2.0 | 1 (shift) | ~1 | ~4-5 | 3.9 MB per layer, memory-bound |

Answer to the brief: yes, the one-token Q8_0 kernels have ALU headroom (bytes per weight 1.06, ~9.4 instructions per
weight), and the engine already uses it: the WS T-forms ARE "one-token GEMV with T accumulators" and the q_b / o_a
M=2/3 launches cost the same as M=1. Where they do not (o_b), the T1R1 form is already near ALU-bound at M=2:
the bit-exact floor is two issued fp32 ops per weight-token (mul, then add) plus the decode, which leaves ~10-15 %
there. The largest remaining excess is not a matrix at all: the FFN pre-norm + mix dots + router chain (+208 / +448
us per check), so that is what ck2-1 targets.

## 3. ck2-1: the FFN chain (pre-norm + mix dot rows + router) at 2-3 tokens

Today per layer at M = 2 / 3: SkNormWM<5120, 16> (2.5 us) + RowsP<RowsPair<TokRows<HcDotsRows<5120, 8>>,
DenseRowsG<GemvH16P<160>, G>>> (router rows, the mix's 25 dot rows per token riding as sub-group rows with a serial
double chain each: 14.4 / 19.3 us). The router alone is 9.7 / 10.2 us: the riding dot rows cost 4.7 / 9.1 us.

Forms tried (`src/sycl_v41_ck2.hpp`, bench `src/bench_ck2.cpp`):

* `FlNormKM<M, RF, MODE>`: fl-1's one-launch FlNormK for M tokens. Every router work-group forms the M norm scales
  itself (SkNormSplit partial / finish per token, one barrier; the production chain where the check fails), work-group
  0 writes the normalized vectors; the dot rows are SkDotsFF<8> work-groups (SkDotsWM's, the one-token path's).
  RF 0: one (row, token) per sub-group; RF 1: one row per sub-group with the M tokens' chains side by side (rowg's loop).
  MODE 0: normalized vectors in local memory (M x 20 KiB); MODE 1: x * rs * w formed at every load (FlXF).
* `RowsDotsK<D>` ("rdk"): the norm launch as today, then the rows launch D unchanged (today's router rows) with the
  dot rows as SkDotsFF<8> work-groups in the same launch instead of the HcDotsRows sub-group rows. Generic over D, so
  the same change applies to the attention side's q_a + kv launch (section 5).
* `skdots`: SkNormDotsWM + plain router (the existing runtime switch OWN_MT_SKDOTS_MIN = 2 / 3).

ISA (`isa/b2`, `isa/b4i`): all FlNormKM forms 128-register except RF1 MODE1 at M = 5 / 6 (256: not used);
RF0 MODE1 at M >= 3 keeps rs in private memory (scratch sends; not used). FlNormKM<2, 1, 1>: 128 registers, no
scratch.

## 4. Bench numbers (card 3, real rows of layers 2 and 30, 16 weight copies, median of 9 rounds x 59 chains, us)

Chain span (first start .. last end) per layer; layers 2 and 30 agree within 0.1 us.

| form | M=2 | M=3 | M=4 (ND=1) | M=5 (ND=1) | M=6 (ND=1) |
|---|---|---|---|---|---|
| today (SkNormWM + router with HcDotsRows riding) | 16.98 | 21.98 | (24.58) | (25.62) | (32.92) |
| skdots (SkNormDotsWM + router; engine's form at M >= 4) | 16.77 | 19.06 | **16.88** | **18.02** | **18.02** |
| FlNormKM RF1 MODE1 (k1m1) | **13.02** | 22.19 | 21.35 | 21.35 | 24.69 |
| FlNormKM RF1 MODE0 (k1m0), router work-groups first | 14.79 | 17.40 | 24.48 | 30.42 | 30.62 |
| FlNormKM RF0 MODE1 / MODE0 | 16.56 / 17.29 | 29.06 / 35.52 | 26.67 / 43.33 | 35.52 / 64.69 | 63.54 / 87.92 |
| rdk: SkNormWM + RowsDotsK<router G = tgm(M)> | 15.42 | **16.56** | 16.56 | 17.50 | 17.50 |
| rdk with G = 1 / 2 | 15.42 / - | 22.29 / 16.56 | 16.25 / 16.56 | 21.56 / 17.50 | 23.12 / 17.50 |

(M >= 4: ND=1 = one card's share of the dot rows under OWN_MT_DSPLIT; there the engine runs skdots, so skdots is the
baseline. The timing sets had no SkDotsFF fallback row; a fallback row costs ~+6 us on its launch, ~1 % of launches on
real data per SkDotsFF's comment, the same exposure as the engine's one-token path and its M >= 4 blocks.)

Without dot rows (ND=-1), to split the costs: M=2 norm + router 12.5 (two launches) vs FlNormKM 12.3; M=3 13.0 vs
k1m1 16.0 / k1m0 15.2. So at 3 tokens the per-work-group norm prologue (three norms on each of 24 work-groups) and the
x * rs * w loads cost more than the separate norm launch; at 2 tokens the fold wins and the dot work-groups hide
almost fully behind the router rows (13.0 with them, 12.3 without).

Picks: M=2 FlNormKM<2, 1, 1> (-3.96 us per layer); M=3 rdk with today's G (-5.42 us per layer); M >= 4 nothing
worth it (rdk vs skdots -0.3 .. -0.5 us per layer, and only with OWN_MT_SKDOTS_MIN raised).

Bitwise (every variant vs today, fresh poisoned buffers, outputs xn, logits, and the FFN mix finish's pre / post /
comb computed from each form's partials): runs bw1, t1, t2: 0 differing of 7,940 buffers compared, M = 2 .. 6, both
layers, real-like sets, N(0, 1) stream sets (SkDotsFF fallback rows present: 0-24 per run, compared too) and
forced-midpoint norm sets (host distance 1e-17 .. 4e-15 relative: the SkNormSplit check fails, the chain runs).
Kernel journal clean after every run (`logs/kj-*.txt` empty).


## 5. The attention side's q_a + kv launch with RowsDotsK (measured, not taken)

`PAIR=1` in the bench: the q_a + kv rows (1,280 + 512 x 5,120) in the forms gemv_pair_m picks at 2-3 tokens
(OWN_MT_WS + OWN_MT_CK defaults; the bench prints them: Q8_0 M2 T2R1P5 + T1R1, M3 T3R1 x 2; Q6_K M2 T2R1P5 x 2, M3
T3R1 x 2, the same as tl105's timeline), today's HcDotsRows riders against RowsDotsK, layers 0 (Q8_0) and 27 (Q6_K):

| pair launch, us | M=2 today | M=2 RowsDotsK | M=3 today | M=3 RowsDotsK |
|---|---|---|---|---|
| Q8_0 (27 layers) | 22.29 | 25.21 | 24.06 | 28.54 |
| Q6_K (13 layers) | 23.65 | 21.56 | 26.98 | 27.81 |

Bitwise 0 of 160 differ (q_a, kv, finish outputs). The weight-stationary pair forms hide the riding sub-group rows
better than the SkDotsFF work-groups (which take whole Xe-cores from the pair's row blocks), so the patch applies
RowsDotsK to the router only (the Q6_K M2 gain, 13 x 2.1 = 27 us per check, is too small to carry a second path).

## 6. Predicted saving per check (card 2; the FFN chain runs alike on every card, between exchanges)

Bench gain per layer x 40 layers x the engine/bench ratio of today's chain (tl105 18.7 / 16.98 = 1.10 at M=2,
24.7 / 21.98 = 1.12 at M=3):

| M | today (bench) | ck2-1 (bench) | per check |
|---|---|---|---|
| 2 | 16.98 us | 13.02 (FlNormKM<2, 1, 1>) | **-0.17 ms** (13.3 ms check: -1.3 %) |
| 3 | 21.98 us | 16.56 (SkNormWM + RowsDotsK<DenseRowsG<GemvH16P<160>, 3>>) | **-0.24 ms** (15.7 ms: -1.5 %) |
| 4 | skdots 16.88 | unchanged by default | 0 (rdk with OWN_MT_SKDOTS_MIN raised: ~-0.02 ms, not worth a path) |

SkDotsFF fallback rows (+~6 us on a launch that has one; ~1 % of 25-row launches on real data) cost about
0.2 us per layer on average at 2-3 tokens: inside these numbers' margin, and the same exposure the one-token path
and the M >= 4 blocks already carry. With tl105's check mix on card 2 (per 100 checks: 30 of M2, 20 of M3) that is
~10 ms per 100 checks of ~1.4 s check time: ~0.7 % guessing speed, short of the brief's ~5 % target. The rest of the
M2/M3 excess sits in o_b (+92 / +232 us), the attention norm + dots + q_a/kv (+105 / +220) and q_b Q6 (+34 / +65).

## 7. Patch: `/home/steve/dsv41-work/ck2/ck2-1.patch` (opt-in, OWN_CK2)

Against the engine tree at 2613d1aa3 (tp105); `git apply --check` ok from the lab repo root; the patched runner
passes the tp105 build's `-fsyntax-only` step (`syn.sh`, `logs/syntax-ck2.log`; helpers do not build the runner).
Generated by `mkpatch.py` from `patch/a` (tree copies) and `patch/b` (edited copies). Four files:

* new `kernels/sycl_v41_ck2.hpp`: FlNormKM<M, RF, MODE>, RowsDotsK<D>, rows_dots() (the bench's header);
* `backend/backend_sycl_v41.hpp`: the include;
* `backend/backend_sycl_v41_mt.inc`: mt_ck2 / mt_ck2_forms, ck2_on(), ck2_dots<DK>() (RowsDotsK, router rows only:
  DK = GemvH16P<160>, rider TokRows<HcDotsRows<5120, 8>>), ck2_launch(); dense_m's rider launch tries ck2_dots first;
  tpm_layer's phase 3 tries ck2n (FlNormKM<2, 1, 1>, M = 2 only) before today's norm / dots / router launches;
* `planning/dsv41-fixtures/own_run_v41.cpp`: OWN_CK2 (1 = sizes 2, 3; n = mask, bit M - 2), OWN_CK2_MS="2,3",
  OWN_CK2_FORMS (default 3: 1 the M2 fold, 2 the router's dot rows as work-groups; at M2 bit 1 takes precedence).

Not taken (falls back to today's launches): the draft's steps, an armed exchange tail (OWN_XTAIL), mt_small off,
an unpacked / non-F32 / non-5,120 router, unaligned buffers. Under OWN_MT_DSPLIT (if lowered to 2-3) the dot rows
cover this card's tokens into the arena, as skmix / dmix do.

Exactness: one card, real rows, every output word: FlNormKM and RowsDotsK vs today's launches 0 of 8,100 buffers
differ (runs bw1, t1, t2, t3; ALL lines in `logs/out-*.txt`); both picks 128-register, no scratch (`isa/b4i`).

### Six-card gate suggestion

* Arms against tp105 BEST (OWN_FL=3 OWN_U3_NOPAIR=1 as tl105): `OWN_CK2=1`; `OWN_CK2=1 OWN_CK2_FORMS=1` (M2 fold
  only); `OWN_CK2=1 OWN_CK2_FORMS=2` (router dot work-groups at M2 and M3).
* Identity: the usual token-identity check (outputs bit-identical to BEST on the code and analysis prompts).
* Speed: check ms by guesses (tools/spec_log_stats.py): expect M2 -0.15..-0.17 ms, M3 -0.2..-0.24 ms, M >= 4 equal.
* One timeline (OWN_TIMELINE_CHECKS on M2/M3 checks, card 2): FlNormKM<2u, 1u, 1u> ~14 us replacing SkNormWM 3.3 +
  router 15.4; RowsDotsK<DenseRowsG<GemvH16P<160u, ActF32>, 3u>> ~15.5 us replacing router + riders 21.3. Note the
  role tools (`tools/roles_by_m.py`) need the two new names.

## 8. Files

* `src/sycl_v41_ck2.hpp` kernels; `src/bench_ck2.cpp` bench (+ `src/gguf_part.inc`); `src/ck2_isa_tu.cpp` census TU
* `build.sh` (guarded icpx), `run.sh` (card-3 share rules: six.active absent 3 min, lock, systemd-run, journal check),
  `syn.sh` (guarded syntax check), `mkpatch.py`, `bin/t2.sh`, `bin/t3.sh` (batched bench invocations)
* `logs/out-bw1.txt` (bitwise), `out-t1.txt`, `out-t2.txt` (FFN timing, M 2-6, decomposition), `out-t3.txt` (pair),
  `kj-*.txt` (kernel journal during each run: empty)
* `tools/kn3.py`, `tools/kn_by_m.py`, `tools/roles_by_m.py`; `roles-card2.txt`, `roles-card0.txt`, `kn-card*.txt`
