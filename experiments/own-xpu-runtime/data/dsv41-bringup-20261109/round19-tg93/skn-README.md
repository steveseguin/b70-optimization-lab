# skn-1: per-token norms of block steps in the one-token path's fast forms (2026-11-11)

Patch: `/home/steve/dsv41-work/skn/skn-1.patch` (against the tp92 snapshot `src92`; `patch -p1` from the engine dir;
checked to apply to `src92` and to the current repo tree, which still equals `src92` for the three files).
Bench: `/home/steve/dsv41-work/skn/bench_skn.cpp` (build `build.sh`, run `run.sh`; logs `r1/` .. `r4/`).
Every switch is OFF by default. Nothing changes until a switch is set.

## Result

- All new forms give the production bits: 7,988 bench comparisons over r1-r4, 0 differ, including 11,323 token
  vectors forced onto the serial-chain fallback (inputs built so the bracket check must fail). No kernel faults.
- At check sizes (2-6 tokens) the 5,120 norm drops from 5.6-7.0 us to 2.7-3.2 us (warm), and fused with its
  `SkDotsWM` rows the pair drops from 10.0 us to 4.6 us. The compressor pools drop from 31.5 us to 2.1 us.
- Expected gain per check: about 0.5-0.6 ms on the card that has a dot token (0.45 ms on the others), so a bit
  more than the 0.3-0.4 ms expected. By the brief's own ratio that is about +2.5-3 % guessing. The gate's A/B
  decides.
- Recommended: `OWN_MT_SKNORM=15 OWN_MT_HCPP=1` (the `OWN_MT_SKNORM_MAX` default of 64 already limits the norm bits).

## Switches

| Switch | What it does | Replaces |
|---|---|---|
| `OWN_MT_SKNORM=mask` | 0 = off (default). Bits below; recommended 15 = bits 1+2+4+8 | |
| bit 1 | a 5,120 norm that runs alone (attention / FFN pre-norm when its dot rows ride elsewhere: `OWN_MT_RIDE`, or `OWN_MT_SKDOTS` without bit 2; the head's output norm) as `SkNormWM<5120, 16>`: one work-group of 16 sub-groups per token, the one-token `SkNormW` code | `RowsP<TokRows<NormRows<5120, 4>>>` |
| bit 2 | where `OWN_MT_SKDOTS` runs (the tp92 default from 2 tokens): the pre-norm and its `SkDotsWM` rows in ONE launch, `SkNormDotsWM<K>` (work-groups 0..m-1 the norms, then the dot rows of the card's token share), as `SkNormDotsW` does for one token | norm launch + `SkDotsWM` launch |
| bit 4 | the q_a 1280 + kv 512 norms where they run alone (`OWN_MT_FIN_QB` / `OWN_MT_DSPLIT`, i.e. every default block) as `SkNormPairWM`: the one-token `SkNormPairW` per token | `RowsP<RowsPair<TokRows<NormRows<1280,4>>, TokRows<NormRows<512,2>>>>` |
| bit 8 | the compressor's ratio-2 pools as `SkCompressPoolWM`: the one-token `SkCompressPoolW` per pooled row | `CompressPoolPM` (31.5 us, a serial chain on one sub-group) |
| bit 16 | the compressor's ratio-1 512 norm as `SkNormWM<512, 2>`. Not recommended: ~0.4 us x 4 per check, loses from 64 tokens | `RowsP<TokRows<NormRows<512, 2>>>` |
| `OWN_MT_SKNORM_MIN` / `_MAX` | block sizes MIN..MAX (defaults 1 / 64). MAX limits bits 1, 2 and 16 only (they lose from ~96 tokens); bits 4 and 8 win at every size measured, up to 256, and take only MIN | |
| `OWN_MT_HCPP=1` | the block's two `HcPostPrePM` launches (attention post + FFN pre, FFN post + next pre) as `HcPostPrePMG`: the item index split by work-group instead of a 64-bit division and modulo of the global id, which the card emulates in software. Off by default | `HcPostPrePM` (same launch shape) |

Where a bit is off, its conditions fail (alignment, sizes, in place), or the norm launch also carries other rows
(e.g. `OWN_MT_RIDE=0` with no SKDOTS: the dot rows ride in the norm's own launch), the production launch runs
unchanged. The draft's `HcPostPrePM` sites (`backend_sycl_v41_draft.inc`) are not touched.

## Why it is bit-identical

- Every new norm launch gives each token one whole work-group, and that work-group runs exactly the code the
  one-token path already runs (`SkNormSplit<5120,16>::run` = `SkNormW`, `SkNormPairW::operator()`, `SkDotsFF::run`,
  `SkCompressPoolW::operator()`) on that token's pointers (the one-token pointers moved by t x the token strides, as
  `TokRows` / `tok_at` do). The weights are shared. No new arithmetic.
- Those one-token forms are already proven and gated to give the production values. The norm's scale is
  `float(1 / sqrt(acc_chain / N + 1e-20))`: the float-float bracket proves it, and where the bracket check fails the
  production chain itself runs. The output is the production expression `w * (x * rs)`. The production block rows
  (`NormRows` with `rs_fast` or the chain) produce the same scale and the same expression, so the outputs match bit
  for bit. `SkCompressPoolW`'s proof covers the pool. `SkDotsFF` is unchanged: the fused launch writes exactly the
  `SkDotsWM` partials, to the same places.
- The fused launch's two parts share no buffer. The norm reads the collapsed stream `x` and writes `xn`; the dot
  rows read the streams and the fn rows and write their partials. Launches before it write both inputs.
- `HcPostPrePMG` is `HcPostPrePM`'s body unchanged. Only the way an item finds its (token, position) differs:
  token = group / (h / 64), position = (group - token x h/64) x 64 + local id, which equals g / h and g % h for the
  64-item work-groups the launch uses (it is taken only when h % 64 == 0).
- Not in place (x != y, checked on the host as for the one-token path). Pointers must be 16-byte aligned, otherwise
  the production launch runs.

## Bench

`bench_skn` builds the production launch (the same `rows_launch` rule, `OWN_MT_RWG=128`) and the new launch on the
same inputs on one card, and compares every output word.

**Inputs:** 20 vector kinds, including real-like activations with outliers and the smallk set. Forced vectors are
built so the float-float sum lands within 3e-12 of a float midpoint, so the fast check must fail and the chain
runs. 8 token sets per size: all real-like, all forced, one forced token, near-midpoint, and NaN/inf ends.
Compressor pools are forced through a -inf second row and a midpoint first row. The fused form is checked with
token shares {all, none, last 1, middle half} for K = 8 and 4.

**Timing:** after a warm-up of 300 back-to-back 256 MiB flush launches (20 more before each row), so the card is at
full clock.
- cold = a 256 MiB cache flush before each launch
- warm = median of back-to-back launches

The tables below are r2 (seed 2, production timed first). All times are us per launch, from `r2/out.txt`.
r3 (seed 3, new form timed first) and r4 (seed 4, the final patch's header) show the same picture. Single-launch
changes vary by up to ~0.9 us between runs (the production 5,120 norm's warm time alone runs 5.6-7.0 us). The
all-token fused launch at 64 varies more (-6.8 to -11.8 us).

**Bitwise runs:**

| run | sizes m | comparisons | differ | forced-chain vectors |
|---|---|---|---|---|
| r1 | 1-6, 16, 64, 256 | 1,216 | 0 | 2,332 |
| r2 | 1-6, 8, 16, 32, 64, 96, 128, 192, 256 | 3,524 | 0 | 5,296 |
| r3 | 2, 5, 16, 64, 128 | 1,290 | 0 | 1,414 |
| r4 (final patch) | 1, 2, 5, 6, 16, 64, 256 | 1,958 | 0 | 2,281 |

**Bit 1: a 5,120 norm alone (`NormRows<5120,4>` -> `SkNormWM<5120,16>`)**

| m | production cold / warm | new cold / warm | warm change |
|---|---|---|---|
| 1 | 12.40 / 6.56 | 3.33 / 3.23 | -3.33 |
| 2 | 13.02 / 6.88 | 3.44 / 3.23 | -3.65 |
| 3 | 12.50 / 6.77 | 3.33 / 3.12 | -3.65 |
| 4 | 10.62 / 5.62 | 2.92 / 2.71 | -2.92 |
| 5 | 10.52 / 5.62 | 2.92 / 2.71 | -2.92 |
| 6 | 12.81 / 6.98 | 3.54 / 3.23 | -3.75 |
| 16 | 10.31 / 5.73 | 3.44 / 2.81 | -2.92 |
| 32 | 12.61 / 7.29 | 5.00 / 3.96 | -3.33 |
| 64 | 13.65 / 8.33 | 7.50 / 5.21 | -3.13 |
| 96 | 13.96 / 8.65 | 10.42 / 9.17 | +0.52 |
| 128 | 11.67 / 7.08 | 11.77 / 10.31 | +3.23 |
| 256 | 21.77 / 14.38 | 23.64 / 17.08 | +2.71 |

**Bit 2: 5,120 pre-norm + its `SkDotsWM<8>` rows, the card's DSPLIT token share (production = two launches)**

| m | production cold / warm | new cold / warm | warm change |
|---|---|---|---|
| 2 (1-token share) | 16.56 / 10.00 | 6.46 / 4.58 | -5.42 |
| 3 (1-token share) | 16.46 / 10.00 | 6.35 / 4.58 | -5.42 |
| 4 (1-token share) | 16.56 / 10.00 | 6.46 / 4.58 | -5.42 |
| 5 (1-token share) | 16.46 / 10.00 | 6.46 / 4.58 | -5.42 |
| 6 (1-token share) | 16.46 / 9.79 | 6.46 / 4.58 | -5.21 |
| 16 (3-token share) | 19.48 / 14.06 | 9.79 / 8.12 | -5.94 |
| 64 (11-token share) | 40.94 / 35.00 | 28.23 / 25.21 | -9.79 |
| 96 (16-token share) | 49.38 / 43.02 | 37.71 / 34.48 | -8.54 |
| 128 (22-token share) | 58.33 / 51.15 | 54.48 / 52.19 | +1.04 |
| 256 (43-token share) | 98.44 / 91.56 | 94.69 / 92.71 | +1.14 |

On a card whose share has no tokens, the fused launch is the norm alone (the bit 1 row).

**Bit 2, every token's dot rows on the card (`OWN_MT_DSPLIT=0`)**

| m | production cold / warm | new cold / warm | warm change |
|---|---|---|---|
| 2 | 17.81 / 11.98 | 7.40 / 6.04 | -5.94 |
| 3 | 19.89 / 14.17 | 9.17 / 7.81 | -6.35 |
| 4 | 22.40 / 16.77 | 11.56 / 10.31 | -6.46 |
| 5 | 23.33 / 17.19 | 14.06 / 11.98 | -5.21 |
| 6 | 31.46 / 25.31 | 19.90 / 18.85 | -6.46 |
| 16 | 48.96 / 42.92 | 36.35 / 34.27 | -8.65 |
| 64 | 127.60 / 119.90 | 116.15 / 112.71 | -7.19 |
| 128 | 233.54 / 226.15 | 234.17 / 230.42 | +4.27 |

**Bit 4: q_a 1280 + kv 512 norms (`RowsPair<NormRows<1280>, NormRows<512>>` -> `SkNormPairWM`)**

| m | production cold / warm | new cold / warm | warm change |
|---|---|---|---|
| 2 | 4.06 / 2.81 | 2.19 / 1.98 | -0.83 |
| 5 | 4.06 / 2.81 | 2.19 / 1.98 | -0.83 |
| 16 | 3.96 / 2.81 | 2.29 / 1.98 | -0.83 |
| 64 | 4.79 / 3.75 | 2.92 / 2.40 | -1.35 |
| 128 | 6.35 / 5.62 | 4.27 / 3.44 | -2.19 |
| 256 | 9.38 / 8.02 | 6.98 / 5.52 | -2.50 |

**Bit 8: compressor ratio-2 pools (`CompressPoolPM` -> `SkCompressPoolWM`)**

| m | production cold / warm | new cold / warm | warm change |
|---|---|---|---|
| 2 | 39.06 / 31.35 | 2.60 / 2.08 | -29.27 |
| 5 | 38.85 / 31.56 | 2.60 / 2.08 | -29.48 |
| 16 | 38.65 / 31.56 | 2.60 / 2.08 | -29.48 |
| 64 | 38.33 / 31.67 | 2.81 / 2.29 | -29.38 |
| 128 | 38.23 / 31.67 | 3.85 / 3.12 | -28.54 |
| 256 | 37.92 / 31.35 | 6.25 / 5.21 | -26.14 |

**Bit 16 (not recommended): compressor ratio-1 512 norm (`NormRows<512,2>` -> `SkNormWM<512,2>`)**

| m | production cold / warm | new cold / warm | warm change |
|---|---|---|---|
| 2 | 2.50 / 2.08 | 1.98 / 1.67 | -0.42 |
| 5 | 2.50 / 2.08 | 1.98 / 1.67 | -0.42 |
| 16 | 2.50 / 2.19 | 1.98 / 1.77 | -0.42 |
| 64 | 2.60 / 2.08 | 3.12 / 2.81 | +0.73 |
| 128 | 3.54 / 3.12 | 4.79 / 4.48 | +1.35 |
| 256 | 3.65 / 3.23 | 8.33 / 7.60 | +4.38 |

**`OWN_MT_HCPP=1`: `HcPostPrePM` -> `HcPostPrePMG`**

| m | production cold / warm | new cold / warm | warm change |
|---|---|---|---|
| 2 | 1.98 / 1.35 | 1.56 / 1.04 | -0.31 |
| 3 | 2.08 / 1.46 | 1.67 / 1.04 | -0.42 |
| 4 | 2.19 / 1.67 | 1.88 / 1.15 | -0.52 |
| 5 | 2.50 / 1.77 | 2.08 / 1.25 | -0.52 |
| 6 | 2.60 / 1.88 | 2.19 / 1.25 | -0.62 |
| 16 | 4.69 / 3.65 | 4.27 / 2.19 | -1.46 |
| 64 | 13.12 / 8.44 | 12.50 / 4.58 | -3.85 |
| 128 | 24.27 / 15.31 | 23.33 / 8.02 | -7.29 |
| 256 | 57.19 / 53.86 | 56.15 / 48.75 | -5.11 |

**Fallback cost: every token forced onto the serial chain**

The fallback runs only when a token's sum lands within the 4e-12 band of a float midpoint; the bench forces it.
With every token forced, the new 5,120 form is slower (each token's work-group runs the chain alone); the q_a + kv
form stays faster. The gate's speed A/B covers the real rate.

| m | production cold / warm | new cold / warm | warm change |
|---|---|---|---|
| 1, 5,120 norm | 22.19 / 15.31 | 18.65 / 15.42 | +0.10 |
| 1, q_a + kv norms | 6.56 / 5.31 | 4.48 / 4.48 | -0.83 |
| 5, 5,120 norm | 17.92 / 12.92 | 15.83 / 15.52 | +2.60 |
| 5, q_a + kv norms | 6.46 / 5.42 | 4.48 / 4.27 | -1.15 |
| 64, 5,120 norm | 32.08 / 25.31 | 39.58 / 30.83 | +5.52 |
| 64, q_a + kv norms | 9.27 / 8.23 | 7.08 / 6.46 | -1.77 |

### Expected gain

**Per check.** Launch counts per check and card come from the tg91 check timeline
(`/home/steve/dsv41-work/runs/tg91/tl_ck.txt`, card 2, M = 2/4/5, `an/ck_names.py`). Each is multiplied by the
bench's warm change.

| Launch (count per check) | Saving per check |
|---|---|
| 5,120 norms (82): 77 fused with their dot rows, 5 alone | 77 x 5.4 + 5 x 3.5 = 0.43 ms on the card with a dot token; 82 x 3.5 = 0.29 ms on a card with none |
| q_a + kv norms (40) | 40 x 0.83 = 0.03 ms. In situ the production launch averaged 4.0-4.2 us, so up to 0.08 ms |
| compressor pools (3) | 3 x 29.4 = 0.09 ms |
| `HcPostPrePM` (78) | 78 x 0.31-0.62 = 0.02-0.05 ms |

Total: about 0.5-0.6 ms per check on the card with a dot token, about 0.45 ms on the others.

**Prompt blocks of 64 tokens (3K read):** 77 x 9.8 + 3 x 29.4 + 40 x 1.35 + 78 x 3.85 ≈ 1.2 ms per block.
Blocks of 128-256 tokens keep the production 5,120 / 512 norms (MAX = 64) but still gain from bits 4, 8 and HCPP:
about 0.6-0.75 ms per block.

## Closed in this round

- `ExpertGroupM` -> `ExpertGroupSG` (one sub-group, ids in registers): bit-identical (200 of 200 launches at every
  m), but no gain at 12-30 slots and much slower above (6 tokens: 4.79 -> 13.12 us; 16 tokens: 12.08 -> 86.35 us).
  It is kept only in the bench file, not in the patch.

| m | production cold / warm | new cold / warm | warm change |
|---|---|---|---|
| 2 | 3.23 / 2.81 | 3.44 / 2.40 | -0.42 |
| 3 | 3.85 / 3.33 | 4.17 / 3.02 | -0.31 |
| 4 | 4.27 / 3.75 | 4.90 / 3.75 | +0.00 |
| 5 | 5.00 / 4.58 | 5.83 / 4.58 | -0.00 |
| 6 | 5.62 / 4.79 | 14.06 / 13.12 | +8.33 |
| 16 | 12.92 / 12.08 | 87.19 / 86.35 | +74.27 |

- `SwigluBothSM`: already a per-token form. Its growth with m is real elementwise work, so nothing fixed to remove.
- Bit 16: built and exact, but it saves only ~1.7 us per check (4 x 0.42) and loses from 64 tokens. Leave it off.

## What the gate must cover

Run with `OWN_MT_SKNORM=15 OWN_MT_HCPP=1`, plus each bit alone (1, 2, 4, 8) and HCPP alone if anything differs (to
bisect).

1. **Prompt-1 traces byte-identical to production** at blocks 1, 5, 16, 64 and 256, in the h5 and h64 configs.
   - 1, 5 and 16 exercise every bit.
   - 64 is the last size with bits 1/2/16 on.
   - 256 runs only bit 4 (where DSPLIT runs), bit 8 and HCPP.
   - Also once with `OWN_MT_SKNORM_MAX=256`, to cover bits 1/2 at 128-256.
2. **The same traces with the paths that change which norm form runs:**
   - `OWN_MT_SKDOTS=0` with `OWN_MT_RIDE=1`: bit 1 at both pre-norms, no fusion.
   - `OWN_MT_SKDOTS=4`: the fused form with K = 4.
   - `OWN_MT_DSPLIT=0`: every token's dot rows fused on each card.
   - `OWN_MT_RIDE=0` with `OWN_MT_SKDOTS=0`: production norm-with-dots launch, the bits must stay out.
   - `OWN_MT_FIN_QB=0 OWN_MT_DSPLIT=0`: the q_a/kv norms ride with the finish, so bit 4 must stay out.
3. **3K traces** at blocks 64 and 128, byte-identical.
4. **Answers** at 40, 128 and 256 tokens, the same as production.
5. **Guessing runs** (code, analysis and 3K prompts) SAME AS plain, with guess logs equal to production's.
6. **Speed:** A/B for checks (guessing tok/s) and the 3K read, plus one check timeline. The timeline should show
   - `SkNormWM` / `SkNormDotsWM` / `SkNormPairWM` / `SkCompressPoolWM` / `HcPostPrePMG` in place of
     `NormRows<5120>`, `NormRows<1280>+<512>`, `CompressPoolPM` and `HcPostPrePM`
   - no `SkDotsWM` launches left where bit 2 runs.
7. **Kernel log** clean after each run.
