# Round 19, gates tg96 + tg96b (build tp96, 2026-11-11)

tp96 = tp95 (807e732f2) + k7-1 (`OWN_K7`), rux-1 (`OWN_MT_RUX`), ck-2 (`OWN_MT_CK` mask, `OWN_MT_CK_MS`,
`OWN_MT_CK_FIN`) and attn-a2 (`OWN_ATT_T=1`). Everything is opt-in in tp96. tg96 ran the traces and stopped at a
global exit after the K7 arms failed; tg96b continued from tg96's trace results with per-patch flags. tg96b ended
at 13:31:22 (ALLDONE).

## In plain words

- **New attention kernel (`OWN_ATT_T=1`): works and is faster.** Normal writing 101.2 / 101.4 tok/s vs 99.5 / 97.9.
  After a 3K prompt it writes 92.9 / 93.0 vs 87.5 / 90.5. Every trace identical, every answer the same.
- **Cheaper checks (`OWN_MT_CK=1`, ck-2): works, +3 %.** A 2-token check costs 13.37 ms instead of 14.07 (median).
- **Both together:** code 139.2 / 139.3 tok/s (was 133.0 / 133.4), analysis 153.8 / 153.6 (was 146.9 / 148.0),
  prose 117.3 (was 111.8), guessing after a 3K prompt 142.2 (was 131.2). All the same answers as without guessing.
- **Faster expert kernels for prompts (`OWN_MT_RUX=1 OWN_MT_RUX_CAP=6`): +5 % prompt reading.** 3K prompt read in
  6.73 s, 497 tok/s, vs 7.09 s, 472 tok/s. Larger prompt blocks (128, 256) add almost nothing (497, 499).
- **K7 (mix sums riding the exchanges) failed:** every K7 run stopped with "exchange timed out". The helper's
  k7-2 fixes the cause (cache lines shared between cards, reads in the waiting launch). Not in tp96's results.
- **The runtime switches tried with ck (`OWN_MT_XPUSH=0/2`, `OWN_XPULL_MIN=6912`, `OWN_MT_SKDOTS_MIN=2/3`,
  `OWN_MT_FIN_QB=0`) give nothing:** all within ±0.2 % of ck alone, or slower (`XPUSH=2` -3.9 %, `FIN_QB=0` -0.9 %).
  The per-M mask that skips 3-token checks (`OWN_MT_CK_MS=2,4,5,6`) is slower than the full mask (136.2 vs 137.5).

## Correctness

tg96b: 7 TRACE_IDENTICAL, 7 IDS40_SAME, 7 SPEED128_SAME, 12 ANSWER256_SAME, 38 guessing runs "SAME AS the plain",
34 GLOG_SAME (the guess log equals the default run's, so the same guesses were kept), no DIFFER, no fault lines.
tg96: 36 TRACE_IDENTICAL; the 9 TRACE_DIFFERS are all K7 runs (h1k7, h1k71, h1k72, h5k7, h16k7, h64k7, h256k7,
h1attk7, h5all), each ended by "card-to-card exchange timed out". `h5attck` (ATT + CK, 5-token blocks) was identical.

## Speeds (tg96b, `summary.txt`)

| run | round 1 | round 2 |
|---|---|---|
| plain 128 tokens, tp95 defaults (a95) | 97.78 | 97.94 |
| plain, tp96 defaults (d96) | 99.49 | 97.87 |
| plain, ATT | 101.22 | 101.44 |
| 3K read, d96 | 472.1 (7.09 s) | 471.5 |
| 3K read, ATT | 472.0 | 471.4 |
| 3K read, RUX | 497.1 (6.73 s) | 496.8 |
| 3K read, RUX, block 128 | 497.4 | 497.3 |
| 3K read, RUX, block 256 | 499.3 (6.68 s) | 498.7 |
| 3K read, block 256, EU_BIG=0 | 469.9 | 469.9 |
| writing after 3K, d96 | 87.52 | 90.45 |
| writing after 3K, ATT | 92.93 | 93.00 |

Guessing, 511 tokens, tok/s (check ms per cycle):

| prompt | d96 | ATT | CK | CK_MS=2,4,5,6 | CK_FIN only | ATT + CK |
|---|---|---|---|---|---|---|
| code r1 | 133.01 (15.28) | 134.92 (15.04) | 137.48 (14.74) | 136.29 (14.90) | 135.25 (14.99) | 139.24 (14.53) |
| code r2 | 133.37 (15.24) | 134.91 (15.04) | 137.49 (14.74) | 136.18 (14.91) | | 139.30 (14.53) |
| analysis r1 | 146.94 (17.37) | 149.15 (17.08) | 152.14 (16.72) | 151.16 (16.85) | 149.31 (17.05) | 153.80 (16.52) |
| analysis r2 | 147.97 (17.23) | 149.11 (17.08) | 152.45 (16.69) | 150.97 (16.87) | | 153.64 (16.54) |
| prose | 111.81 (15.31) | | | | | 117.27 (14.51) |
| after 3K prompt (255 tokens) | 131.20 (18.51) | | | | | 142.19 (16.95) |

CK + runtime switch (one run each), code / analysis tok/s: XPUSH=0 137.18 / 152.42; XPUSH=2 132.12 / 147.83;
XPULL_MIN=6912 136.81 / 151.25; SKDOTS_MIN=2 137.66 / 152.13; SKDOTS_MIN=3 137.64 / 152.24; FIN_QB=0 136.29 / 151.46.

Check cost by number of guesses (code prompt, median ms), from `check-cost-by-guesses.txt`:

| guesses (tokens checked) | 0 (1) | 1 (2) | 2 (3) | 3 (4) | 4 (5) | 5 (6) |
|---|---|---|---|---|---|---|
| d96 | 10.54 | 14.07 | 16.66 | 18.39 | 21.19 | 23.06 |
| CK | 10.60 | 13.37 | 15.71 | 17.85 | 20.30 | 22.53 |
| ATT + CK | 10.41 | 13.05 | 15.45 | 17.59 | 20.28 | 22.66 |

## Decision for tp97

Defaults on: `OWN_ATT_T=1`, `OWN_MT_CK=1` (all check sizes), `OWN_MT_RUX=1` with `OWN_MT_RUX_CAP=6` (prompt
launches of 16 or more tokens only). Prompt block stays 64. The runtime switches stay as they are.

## Files

- `tg96-summary.txt`, `tg96b-summary.txt`: the gates' summaries.
- `spec/`: every guessing run's spec log (one line per check).
- `check-cost-by-guesses.txt`: `spec_log_stats.py` for d96 and ATT + CK on code, analysis, prose and 3K.
- `gprof_one.log`, `gprof_ck.log`: card-2 kernel profiles (one-token decode with ATT; checks with ATT + CK).
- Scripts: `../round18-scripts/strategy/build96.sh`, `tg96.sh`, `tg96b.sh`.
- Timelines (`tl_one`, `tl_one_d`, `tl_ck`, `tl_ck3`, `tl_ck3_d`, 5-6 MB each) stay in `/home/steve/dsv41-work/runs/tg96b`.
