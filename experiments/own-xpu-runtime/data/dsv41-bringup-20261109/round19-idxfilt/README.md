# idxfilt: a proven-bound pre-filter for the index scores (2026-11-17)

## Why

At long context the indexer scores every earlier row for every token: 4,096 FP32 multiply-adds per row and token
(32 heads x 128 dims, then a weighted sum over heads), in a fixed order so every list stays bit-identical. The
scoring bench (`round19-privmem`, c126 `tsx3`) puts one card's 43-token prompt share at 993K rows at 43.5 ms
(layer 20, 993K rows) + 3 x 22.3 ms (layers 2 / 8 / 14, 496K rows): about 110 ms per 43 tokens per card at the end
of a 1M prompt, about **210 s of the 1,764 s 1M read** (c127 `s1m_dk`). The same scores cost the checks ~0.6 ms per
checked token at 1M and the one-token steps ~0.9 ms per step. The engine never used the matrix engines (DPAS),
because their sums are not in our fixed order.

## The idea (no change to any list)

Compute every row's score approximately on the matrix engines, with a bound on the error that is proven, not
estimated; then score exactly only the rows that the bound cannot rule out, and run the unchanged selects.

- Approximate score `s~`: the query split into two BF16 parts (`q = hi + lo + r`, `|r| <= 2^-16 |q|`); the key rows
  are BF16 already, so each product is exact; the sums in any order (DPAS), FP32.
- Bound: `|s - s~| <= E = C * ||k||_2 * ||a||_2`, `a_i = sum_h |w_h| |q_hi|`, `C = 2e-4`.
  Error terms against `B = sum_i |k_i| a_i` (`<= ||k||_2 ||a||_2`, Cauchy-Schwarz): the exact order's own FP32
  rounding `gamma_129 + gamma_33` (~9.7e-6), the BF16 split `2^-16` (1.5e-5), the DPAS sums taken as 4x worse than
  FP32 rounding over 257 terms (`257 * 2^-22` = 6.1e-5), the FP32 head sum of `s~` (`gamma_33`, 2e-6): < 9e-5 in all.
  `C = 2e-4` leaves a 2.2x margin, which also covers the FP32 rounding of the norms, of `LO` and of `HI`.
- Selection: `LO = s~ - E <= s <= HI = s~ + E`. With `L` = the K-th largest `LO` (K = 512 rows; 2048 block keys at
  layer 20, a block's key = the largest of its 8 row values), at least K rows have `s >= L`, so the K-th largest
  exact score `s_K >= L`; any row with `s >= s_K` has `HI >= L`. So: exact scores for every row with `HI >= L` (and
  every row of a block whose largest `HI` reaches `L_b`), `LO` left in the others. Every row left at `LO` has
  `LO <= HI < L <= s_K`: strictly below every row the select can keep, never tied with one. The selects (score
  descending, the lower row first among equal scores) keep the same rows, blocks and marks, bit for bit. The newest
  block (kept at +inf) only lowers `L_b`: more rows scored exactly, never fewer.
- `L` comes from the unchanged selects run once on `LO` (the smallest `LO` among the rows they keep is exactly the
  K-th largest; `L_b` likewise from the block list), so no new select kernel is needed: selects on `LO`, then
  `IdxFiltX` (exact scores where needed, `IndexerScoreB::run`'s sums in its order), then the selects again.

Random-data estimate (`/home/steve/dsv41-work/idxfilt/analyze.py`, 20,000 rows, this exact bound): two BF16 passes
leave 547 rows for exact scoring (one pass: 3,181; so two passes). Real distributions come from `OWN_IDX_DUMP`.

## Code (engine worktree, tp129 sources 10f1b390ab)

- `src/stage2/packet3/kernels/sycl_v41_idxfilt.hpp`: `IdxFiltQ` (the query's BF16 parts as B matrices, the bound
  factor per token), `IdxFiltS<RT>` (joint_matrix 8 x 16 x 16 BF16 tiles, `LO` into the score rows, row norms),
  `IdxFiltX` (thresholds from the first selects, exact scores where a row can still be kept).
- `backend_sycl_v41_mt.inc`: prompt halves' split layers 2 / 8 / 14 / 20 from `OWN_IDX_FILT_MIN` rows (default
  32,768): `ifl_score`, the selects, `ifl_exact`, the selects again. `OWN_IDX_FILT=2`: also every row exact and the
  unchanged selects into shadows, every list / block list / mark compared ("OWN_IDX_FILT=2 check: ... ALL SAME").
- `OWN_IDX_DUMP=prefix OWN_IDX_DUMP_MIN=rows`: card 0's one-token index inputs per split layer (real data for the
  bound's tightness).
- `tools/bench/test_idxfilt.cpp`: the bound on every row against `IndexerScoreBM`, rows left, times against
  `IndexerScoreBM` / `IndexerScoreBMS<2>` rmaj, and the selects end to end (exact vs filtered: every list, block list
  and mark).

## Gate (c129, queued after the tp129 build)

Bench (prompt shape 43 tokens at 95K / 352K / 993K; checks 6 / 3 tokens), the dump at 194K and the bench / analysis
on it, the engine's check mode at 95K from 8,192 rows (must be ALL SAME), x95k default vs filter, x200k with the
filter against R200, x1m read with the filter + kvshard against x1m_a.

## Next, if it holds

The one-token (dtopk-1) and check (dtopk-2) paths: the same pre-filter per stage-1 work-group (each work-group's
512th largest `LO` from its own stage-1 list is a valid threshold for its rows, so its candidates and the merge stay
the same), keys read once for all of a check's tokens.
