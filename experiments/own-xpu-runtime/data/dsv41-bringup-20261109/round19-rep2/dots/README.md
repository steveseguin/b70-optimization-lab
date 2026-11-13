# rep2 dots: a faster form for the one-token dot-row launches, one card, same bits (helper rep2, 2026-11-13)

Status (keep current): **DONE 12:49. Stopped at the line: even a perfect same-bits form of these two launches saves
at most ~0.12 ms per one-token step (section 6, measured read floors); the best form found (T1, bit-identical) saves
0.31-0.32 us per attention launch = ~0.012 ms per step. No engine patch, no build, no six-card run.**

Brief (coordinator, 11:40): the FFN pre-norm launch FlNormK (11.88 us in rep2's bench) and the attention one
SkNormDotsW (4.48 us) against 2.50 us for the norm alone; find a faster form with the same arithmetic per output (more
parallelism / less latency), predictions before coding, stop line 0.15 ms per one-token step.
Lab HEAD 68f142fc3 (engine sources identical to 787729bcf, `git diff --stat 787729bcf HEAD -- .../engine/src`: empty);
`dots/tree/` = a fresh copy of them.

## 1. Ledger: the arithmetic of each output (kernels at lab HEAD; file:line in `tree/src/stage2/packet3/kernels/`)

GPU facts used below (to be checked by the bench, which prints them): B70 = 32 Xe cores (the runtime reports 256
compute units = vector engines); a work-group of 512 items = 16 SIMD32 sub-groups on one Xe core; both launches have
at most 49 work-groups, so every work-group starts at once.

**The norm** (SkNormSplit<5120, 16>, sycl_v41.hpp:5573; one work-group, also every router work-group's prologue
fl_norm_scale, sycl_v41_fl.hpp:81): 20 chunks of 256 floats, chunk c on sub-group c % 16 (sub-groups 0-3 two chunks,
4-15 one); lane l holds elements chunk*256 + 32 m + l, m = 0..7. Per lane one float-float block of <= 16 terms
(TwoSum on hi, the low parts in a float chain lo), then acc = acc + double(hi) + double(lo) (2 double adds); the lane
xor tree (5 double add levels, select_from_group); the 16 partials to local memory, ONE barrier; every sub-group sums
them in a fixed xor tree (4 levels), D = 1 / sqrt(acc / N + 1e-20) in double, float(D), a midpoint check (the
production chain RmsNormPS::acc_chain only where it fails). Output w * (x * rs) per element. Longest dependent chain:
16 TwoSum steps (each ~4 dependent float ops on the lo side, 1 on hi) + 2 + 5 + 4 double adds + sqrt + divide.

**A dot row** (SkDotsFF<8>::run, sycl_v41.hpp:5723; 25 per mix: 24 fn rows of 20,480 floats + row 24 = the streams'
sum of squares): one row per work-group; 80 chunks of 256, chunk g on sub-group g % 16 (5 chunks per sub-group, k =
0..4 in order); lane l holds elements g*256 + 32 m + l of the streams (a) and of the fn row (b). Per chunk one block of
K = 8 products p = b a with e = fma(b, a, -p), TwoSum into (hi, lo), then acc = acc + double(hi); acc = acc +
double(lo): per lane a double chain of 10 adds over the 5 chunks in order, and ef = ef + |p| (a float chain of 40).
The lane xor tree (5 levels, double and float), local memory, ONE barrier, a 5-level xor tree over the 16 partials
(lanes >= 16 add 0), the proof check (the production partials HcMixDotsP::row only where it fails, ~1 % of launches);
proven rows write d[8 r] = T, d[8 r + 1..7] = 0. The finish (HcMixFinishSG, another launch) needs float(T) (rows < 24)
and float(1 / sqrt(T / N + 1e-20)) (row 24), so T's bits are what must not change.

**A router row** (fl_h16_sum<160>, sycl_v41_fl.hpp:51; 384 rows of 5,120 bf16-in-16-bit weights = 10,240 B): one
sub-group per row; lane l holds elements 256 s + 32 m + l (s = 0..19, m = 0..7); ONE float chain per lane of 160
terms, sum = sum + w * x (multiply, then add: -ffp-contract=off), in (s, m) order; then sg_tree32 (5 levels, pairs at
distance 1, 2, 4, 8, 16). x = the work-group's local copy of w * (x * rs) (MODE 0). In FlNormK a router work-group of 16
rows first runs fl_norm_scale (the norm's partials, barrier, finish) and fills that local copy (another barrier):
every router work-group's first weight load waits for its own norm prologue.

**The launches**: SkNormDotsW<8> = work-group 0 the norm, 1..25 the attention mix's dot rows (26 work-groups).
FlNormK<5120,16,25,8,0,NoRows,FlH16Rows<160>> = work-groups 0..24 the FFN mix's dot rows, 25..48 the router (16 rows
each, prologue first). Bytes per launch read from memory: attention 1.97 MB (fn rows; the streams 80 KB and x 20 KB
are written by the launch before, cache-hot); FFN 1.97 MB + 3.93 MB = 5.90 MB.

Latency model before measuring (11:55): at ~600 GB/s (256-bit GDDR6 at 19 Gbps; the bench measures what one card
reaches) the bytes alone take 3.3 us (attention) and 9.8 us (FFN); the dependent arithmetic is short against that
(the router's 160-add chain ~0.4-0.6 us at a few cycles per dependent SIMD32 add, the dot chains shorter). So the
model is memory time + the prologue + launch overhead: attention ~1 + 3.3 = ~4.3 us (bench 4.48), FFN ~1 + prologue
1-2 + router bytes 6.5 (the dot rows' 3.3 us overlap the router prologue) = ~9-10 us (bench B0 9.58-10.52 without
the dot rows, 11.77-11.88 with). If that holds, the FFN launch is NOT one dot row's length but the router's bytes
behind its prologue, and the only same-bits levers are (i) the router rows' loads issued before the prologue
(prefetch into the cache: up to the prologue's exposed 1-3 us per layer) and (ii) fewer exposed latencies per dot
work-group (prefetch of its 5 chunks up front: up to ~1 us per layer only if a work-group is latency- not
bandwidth-bound). Predicted at best (i) 0.04-0.12 ms + (ii) 0-0.04 ms per one-token step (40 FFN + 37 attention
launches): around the 0.15 line, so measured first.

Where the counts and engine times come from: `../README.md` section 1 (card 2's one-token trace, round 19): per step
40 FlNormK at 13.45 us each and 37 SkNormDotsW at 6.75 us each. The rep2 bench numbers above (4.48 / 11.88 us) were
taken with 8 weight copies = 15.8 MB, under the card's cache, so partly cache-hot; the engine's are cold (the whole
model streams between two uses of a layer's rows). The same bench showed the attention launch with only 4-5 of its 25
dot rows at 4.38 against 4.48 (`../README.md` section 5, row A): the attention launch's length does not follow its
bytes, which points at one work-group's own read rate (one Xe core) rather than the card's bandwidth.

## 2. Ledger bench (`../src/bench_dots.cpp`, binary `bin/d1`, card 3)

Cold = weight copies cycled over > 3x the cache size the runtime reports; hot = one copy. Variants: empty launches of
1 / 26 / 49 work-groups; N (the norm alone); D1 / D25 (one / 25 dot work-groups); A (production attention launch); R
(router rows alone over a ready vector, GemvH16P<160> as the engine launched it before fl-1: 24 work-groups x 16
rows); R8 / R4 / R1 (the same row body at 8 / 4 / 1 rows per work-group, logits compared); RN (FlNormK without dot
rows); F (production FFN launch); DPsxn (the dot rows' 16 sub-group chains on work-groups of s sub-groups, no combine:
how fast a row's bytes arrive when spread over 1 / 2 / 4 Xe cores); the prefetch forms AP / RNP / FP / FPD
(`tree/.../sycl_v41_dots.hpp`, only prefetches added; every output word compared with production, hot and cold).

## 3. Forms and their predictions (written before the bench ran, 11:40)

Per-step value = (us saved per launch) x 37 (attention) or x 40 (FFN); stop line 0.15 ms.
- P1 router rows prefetched before the norm prologue (FlNormKP; coded, only prefetches): the rows' first 1-2 us of
  memory time overlaps the prologue: FFN -0.5..-2 us cold = 0.02-0.08 ms. Pays alone only at the top of that range.
- P2 dot work-group's 5 chunks prefetched up front (SkDotsPF; coded): -0..-0.5 us per launch (the loads of the
  unrolled loop are independent already, the compiler may issue them early) = 0-0.04 ms over both launches.
- P3 router rows over more work-groups (fewer rows per work-group; each row's chain unchanged, so the same bits by
  construction; NOT coded): pays only if R8 / R4 / R1 << R (a router work-group bound by one Xe core's read rate).
  In FlNormK every router work-group also runs the norm prologue, so the gain is R - R8 at most, minus the extra
  work-groups' share of the cores. Prediction after the ledger.
- P4 a dot row over 2 or 4 work-groups (sub-groups 0-7 / 8-15 on different Xe cores, the 16 partials combined by the
  last work-group in the same xor tree: the same bits by construction; NOT coded): pays only if DP8x1 / DP4x1 <<
  DP16x1 and DP8x25 << DP16x25 (cold). If the attention launch is one dot work-group long (4.38 vs 4.48 above), the
  upper bound is A - N - launch floor, ~1-2 us x 37 = 0.04-0.07 ms; with P1 + P3 on the FFN side the sum could reach
  the line. Prediction after the ledger.

## 4. Ledger bench result (run d1, 11:45, card 3; `../logs/out-d1.txt`, kernel journal empty `../logs/kj-d1.txt`)

Device: "256 compute units, cache 24.0 MiB"; cold = 39 fn-row copies / 20 router copies (> 3 x 24 MiB). Bitwise: 78
comparisons (AP1/AP3, D25P1, FP1/FP3/FPD1/FPD3, RNP1/RNP3, R8/R4/R1 against production, 3 input sets x hot / cold
copy), 0 differ. Kernel us, median of 5 x 39 (timer steps of ~0.104 us):

| variant | cold | hot | reading |
|---|---|---|---|
| E1 / E26 / E49 (empty) | 0.62 / 0.52 / 0.52 | 0.52 | launch floor ~0.5 us whatever the work-group count |
| N (norm alone) | 2.50 | 2.50 | 2.0 us of dependent work above the floor (20 KB, cache-hot) |
| D1 (one SkDotsFF row) | 5.00 | 4.17 | |
| DP16x1 (its 16 chains, no barrier / tree / check) | 3.54 | 2.81 | **the tail (barrier + 16-partial tree + check) = 1.46 cold / 1.36 hot** |
| DP8x1 / DP4x1 (one row over 2 / 4 Xe cores) | 2.50 / 2.50 | 2.50 / 2.50 | one row alone gains 1.0 us cold from 2-4 cores ... |
| D25 / DP16x25 / DP8x25 / DP4x25 | 5.83 / 4.58 / 4.58 / 4.48 | 4.38 / 3.02 / 3.12 / 2.92 | ... but 25 rows do not (P4 dead); 25 rows' tails again 1.25 cold / 1.36 hot |
| A (attention launch) | 5.94 | 4.48 | = D25 + 0.1: the dot rows set it, the norm (2.50) hides under them |
| R (router alone, 24 x 16 rows) / R8 / R4 / R1 | 8.33 / 8.23 / 8.23 / 8.02 | 3.75 / 3.54 / 3.23 / 3.33 | rows per work-group barely matter (P3 dead): 3.93 MB at ~470 GB/s |
| RN (FFN launch, no dot rows) | 10.62 | 5.10 | the norm prologue costs RN - R = 2.29 cold / 1.35 hot |
| F (FFN launch) | 12.08 | 6.98 | the 25 dot rows add 1.46 cold / 1.88 hot |
| D25P1 / AP1 / AP3 (P2) | 7.19 / 7.50 / 7.50 | 5.52 / 5.73 / 5.73 | prefetching the dot chunks: **+1.4 us worse** |
| RNP1 / RNP3 (P1) | 11.35 / 11.35 | 6.35 / 6.35 | router prefetch before the prologue: **+0.7 worse** |
| FP1 / FP3 / FPD1 / FPD3 | 14.48 / 14.48 / 15.94 / 15.94 | 7.81 / 7.81 / 9.17 / 9.27 | worse |

Reading against the model (section 1): (1) the attention launch is not bandwidth-bound and not one row's bytes: 25
rows' chains alone take 4.58 cold (1.97 MB at 430 GB/s), the tail after them adds 1.25-1.46 us, and the launch is
the dot rows (A = D25 + 0.1). (2) The FFN launch is the router's bytes (8.0-8.3 cold) + the norm prologue in front
of them (+2.3 cold) + the dot rows sharing the card (+1.5 cold). (3) Cache prefetch instructions cost more than they
hide here (P1 and P2 lose 0.7-2.4 us); more work-groups per row or fewer rows per work-group do not pay (P3 and P4:
at most 0.1-0.3 us). So the remaining same-bits levers are latency ones: the dot tail (1.3-1.5 us, what is in it is
measured next), the router's first loads ahead of the prologue as real loads (registers, not prefetch), and the
order of the work-groups (router first, so the long rows get Xe cores of their own).

## 5. Predictions for the remaining forms (11:58, before coding) and the bound that decides the stop line

Bound first. Both launches read their weights once from memory, cold; no same-bits form can beat the card's read
rate for those bytes plus the launch floor (0.5 us). The bench's best observed read rates are ~470-490 GB/s (R cold
8.02-8.33 us for 3.93 MB; F cold 12.08 us for 5.90 MB = 488 GB/s); the GDDR6 peak is ~608 GB/s (estimate, 256-bit at
19 Gbps). Measured next: a plain streaming read of the same bytes over many work-groups (BW1 = 1.97 MB, BW3 = 5.90 MB,
cold), which is the floor any form of these launches can reach. If the floors come out near 4.1 us (attention) and
11.2 us (FFN), the most any form can save is (5.94 - 4.1) x 37 + (12.08 - 11.2) x 40 = ~0.07 + ~0.035 = ~0.10 ms per
one-token step: **under the 0.15 ms line even for a perfect form**, and the brief says to write up and stop.

Forms (each the same values in the same order; predictions per launch, cold):
- T1 dot tail through local memory: every lane reads the 16 partials and adds them in the xor tree's own pairs
  ((P0+P1)+(P2+P3))+... and the final + 0.0 of lanes 16..31, no shuffles, no broadcast; same bits by construction
  (commutative pairs, same tree). Saves the shuffles of the 5-level tree and 2 broadcasts: -0.2..-0.6 us of the
  1.3-1.5 us tail, x 37 = 0.01-0.02 ms (attention; the FFN dots share the card's bandwidth, ~0).
- O1 router work-groups first in FlNormK (a work-group index permutation): 0..-0.5 us x 40 = 0-0.02 ms.
- E1 the router rows' first chunks loaded into registers before the norm prologue: the FFN launch is already at
  ~488 GB/s, so -0..-0.9 us x 40 = 0-0.035 ms.
Sum of the three at best ~0.075 ms: under the line.

## 6. Latency / floor bench l1 (12:26, card 3; `../src/bench_lat.cpp`, `../logs/out-l1.txt`, kernel journal empty `../logs/kj-l1.txt`)

Device: "fp64 1, max clock 2800 MHz". Bitwise: T1 against production, 16 comparisons (A vs AT and 25 dot rows, 4
input sets incl. zero streams where every row takes the production partials, hot and cold copies), 0 differ.

**Read floors** (a plain streaming read, the same bytes, cold, 32 / 64 / 128 / 256 work-groups of 512):
BW1 (1.97 MB) 4.38 / 4.17 / 4.38 / 4.38 us; BW3 (5.90 MB) 10.94 / 10.73 / 10.94 / 10.83 us (incl. the launch: BW3
539-550 GB/s, BW1 449-471 GB/s). Against the production launches cold (run d1): attention A 5.94 - 4.17 = **1.77 us** above its floor, FFN F
12.08 - 10.73 = **1.35 us** above its floor. Per one-token step: 1.77 x 37 + 1.35 x 40 = 65 + 54 = **~0.12 ms for a
perfect form** (all compute and latency hidden under the bytes). That is under the 0.15 ms line, so no same-bits form
of these two launches can reach it; by the brief: write up and stop.

Fewer bytes instead: the fn rows are full F32 (`../src/fn_halves.py`, output `../logs/fn_halves.txt`, 12:29: hc_attn_fn 19,660,484 and
hc_ffn_fn 19,660,478 of 19,660,800 values have nonzero low 16 bits over 40 layers; the router ffn_gate_inp 0 of
78,643,200, which is why the engine already stores it halved). So the fn rows cannot be stored in 16 bits losslessly.

**Dependent-op latency** (one sub-group, ns per op; this first pass ran right after start on an idle card, whose
clock is low - f32 add 26.65 ns is ~16 cycles at ~0.6 GHz, not ~75 at 2.8 GHz - so read the ratios; l2 repeats it
with the clock raised): f32 add 26.65; f64 add 87.58, mul 87.53, **div 927.38**, sqrt 203.91; f64 xor-1 shuffle + add
51.78, xor-16 shuffle + add 122.17, broadcast + add 44.30; f32 xor-1 shuffle + add 18.92; float -> double + add 35.76;
the dot's TwoSum element 21.11; a 16-sub-group barrier round trip (2 barriers) 144.30. So F64 add is ~3.3 x an F32
add, and an F64 divide ~35 x: the norm's D = 1 / sqrt(acc / N + 1e-20) is 2 divides + 1 sqrt (~2.1 us at that clock),
the same chain sits in every dot row 24's check, and in every router work-group's norm prologue.

**The dot tail, decomposed (l1 timing ran on the last bitwise set = zero streams, so D / DT / A / AT there all took
the production partials: Dx25 10.52 cold vs 5.83 proven in d1, ~4.7 us for the fallback; l2 re-times on proven
inputs):** DT0x1 (chains + barrier + tree) 3.33 hot, DT1x1 (+ check) 3.54 hot; DT0x25 3.54 hot / 5.10 cold, DT1x25
3.65 hot / 5.21 cold.

## 7. Bench l2 (12:46, card 3; `../logs/out-l2.txt`, kernel journal empty `../logs/kj-l2.txt`): latencies at full clock, T1 timed

Bitwise again 16 comparisons, 0 differ. Timing inputs now nonzero streams (every row proven, the ~99 % path).

**Dependent-op latency with the clock raised** (each pair right after 4 compute-load launches; ns per op): f32 add
3.87 (~11 cycles at 2.8 GHz); f64 add 12.46, mul 12.46; **f64 divide 198.67, sqrt 203.81**; f64 xor-1 shuffle + add
51.68, **f64 xor-16 shuffle + add 122.07** (crossing the two SIMD16 halves); f64 broadcast + add 44.20; f32 xor-1
shuffle + add 18.77; float -> double + add 35.65; the dot's TwoSum element (f32, hi and lo chains) 21.01; a 16-sub-group
barrier round trip (2 barriers + local store / load + add) 144.25. (The un-warmed passes start at f32 add 26.65 (l1)
/ 17.75 (l2) and reach the same values once the clock is up: the first ops of l1 ran at a low clock.)

**Dot work-group tail, same run** (us, cold / hot):

| | 1 row | 25 rows |
|---|---|---|
| DT0 chains + barrier + SkDotsFF's tree, no check | 4.38 / 3.33 | 5.10 / 3.54 |
| DT1 + the check (no fallback code) | 3.75 / 3.75 | 5.42 / 3.96 |
| D = SkDotsFF (production) | 3.96 / 3.96 | 5.62 / 4.17 |
| DT = SkDotsFT (T1) | 3.75 / 3.65 | 5.31 / 3.85 |
| A = SkNormDotsW<8> / AT = SkNormDotsWT<8> | | 5.94 / 4.48 vs **5.62 / 4.17** |
| D with zero streams (every row takes the production partials) | | 10.52 / 9.06 |

### The latency model (what the coordinator's "2 us / 9.4 us above the norm" is made of)

One dot work-group (one Xe core, 16 threads, in-order issue, so each thread runs at its chain's latency):
the per-lane chain is 40 TwoSum elements (~21 ns each = ~0.84 us) + 10 F64 adds with conversions (~0.24-0.36 us);
the lane tree 5 F64 shuffle levels (xor-16 122 ns + 4 x ~52 = ~0.33 us; the float tree runs alongside); barrier
~0.07; the 16-partial tree 5 levels + 2 broadcasts (~0.33 + 0.09); the check ~0.4 us (DT1 - DT0, 1 row hot); row 24's
check adds 2 divides + 1 sqrt (~0.6 us). Sum ~2.3-2.4 us of dependent latency + launch 0.5 = ~2.8-2.9 against D 1
row 3.96 hot (the rest, ~1.1 us: the loads, 160 KB through one Xe core). With 25 rows cold the bytes (1.97 MB, read floor 4.17 us incl. launch) overlap most of
that latency; A cold 5.94 = the floor + ~1.8 us of exposed tail. The norm (N 2.50) hides under the dot rows: the
attention launch's "2 us above the norm" is the dot rows' tail latency on top of their bytes.

FFN launch: the router's 3.93 MB (R cold 8.33) start only after each router work-group's norm prologue (RN - R =
2.29 cold), whose own chain is ~2.1 us: the 16-element TwoSum chain ~0.34, lane tree ~0.33, barrier, the 16-partial
tree ~0.25, **D = 1 / sqrt(acc / N + 1e-20) = 2 F64 divides + 1 sqrt ~0.6 us**, the check, the local copy + barrier;
plus the 25 dot rows' 1.97 MB sharing the card (F - RN = 1.46 cold). F cold 12.08 against the 5.90 MB read floor 10.73.
So the FFN launch's "9.4 us above the norm" is mostly bytes (the router's), not one dot row's work-group.

### Forms: results and what is left (all below the line; numbers per one-token step)

- **T1 (local-memory tail): bit-identical (32 comparisons over l1 + l2, incl. all-fallback inputs), A 5.94 -> 5.62
  cold, 4.48 -> 4.17 hot: -0.31..-0.32 us x 37 = ~0.012 ms.** Inside its prediction (-0.2..-0.6 us). Code:
  `tree/src/stage2/packet3/kernels/sycl_v41_dots.hpp` (SkDotsFT, SkNormDotsWT); not patched into the engine (alone
  far under the line). In the FFN launch the dot rows are not the long pole: ~0 there.
- P1 / P2 (cache prefetch, section 4): slower by 0.7-2.4 us. P3 / P4 (rows per work-group / a row over more Xe
  cores): 0.1-0.3 us at most, 0 for 25 rows.
- Not built, bounded: O1 (router work-groups first) and E1 (router loads before the prologue) can only win part of
  F's 1.35 us above its read floor (x 40 = 0.054 ms at most); a cheaper sound gate for the norm's D (multiply by
  1/N, one reciprocal square root, inside the check's 4e-12 margin: same rs bits by the existing bracket argument,
  but it needs its own proof) and T1's tree for the norm's 16 partials would take ~0.3-0.5 us off every prologue
  (~0.012-0.02 ms) - all inside the same 0.054 ms FFN bound.
- The bound (section 6) caps all of them together at ~0.12 ms per step (bench conditions, measured floors). Only
  with reads at the nominal ~608 GB/s (my estimate of the peak, not measured) and no compute at all would it be
  0.157 ms ((5.94 - 3.73) x 37 + (12.08 - 10.20) x 40); the best streaming read measured here is 550 GB/s. The engine's own
  launches run 0.8-1.4 us longer than the bench's (`../README.md` section 1: 6.75 / 13.45 us on card 2), but that
  extra comes with the engine's cold weights and is in the floor of any form too.
- Fewer bytes is closed: the fn rows are full F32 (`../logs/fn_halves.txt`).

## 8. Files

- `README.md` (this ledger); `tree/` = lab HEAD engine sources + `src/stage2/packet3/kernels/sycl_v41_dots.hpp`
  (SkDotsPF, SkNormDotsWP, FlNormKP = P1 / P2 prefetch forms; SkDotsFT, SkNormDotsWT = T1).
- Benches: `../src/bench_dots.cpp` (bin `../bin/d1`, out `../logs/out-d1.txt`), `../src/bench_lat.cpp` (bins
  `../bin/l1`, `../bin/l2`; outs `../logs/out-l1.txt`, `../logs/out-l2.txt`), `../src/fn_halves.py`
  (`../logs/fn_halves.txt`). Build logs `../logs/build-d1.log`, `build-l1.log`, `build-l2.log`. Kernel journal during
  each run: `../logs/kj-d1.txt`, `kj-l1.txt`, `kj-l2.txt` (all empty).
