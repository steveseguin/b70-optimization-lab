# Round 19, gate tg100 (build tp100, 2026-11-11) + the overlap check xov2

tp100 = tp99 + qb-off compiled out (`-DOWN41_QBOFF_M` to build it) + xperm-1 (`OWN_PAIR_G128=1`: IQ2_S gate+up at 128
registers) + wa-2 (`OWN_ATT_WA=2`: per-shape window-append choice in checks) + pb-1 (`OWN_PB=1` = mask 0x1e: prompt
blocks of 9-256 tokens with 16-bit rows in weight-reusing forms, counting-sort expert grouping, 6-bit forms without the
private scale array, per-role form + token chunk at 65-256), all opt-in. Build 20:07-20:26 (1129 s); gate 20:26-21:17
(ALLDONE); xov2 21:18-21:19 (ALLDONE).

## In plain words

- **Every trace identical** (35 prompt-1 traces: defaults at 1 / 4 / 5 / 6 / 64 / 128 / 256 tokens, G128, 11 wa-2 arms,
  pb-1 at 1 / 5 / 64 / 128 / 256 and each pb bit alone at 128 and 256, everything together at 5 and 128; 6 3K traces:
  defaults 64 / 256, wa-2 at 64, pb-1 at 64 / 128 / 256). All 25 guessing runs gave the same text as plain writing.
- **pb-1 makes prompt reading 14.6 % faster at blocks of 256** (3K read, whole times, two rounds each, back to back):

  | block | default | `OWN_PB=1` | other |
  |---|---|---|---|
  | 64 | 6.73 / 6.74 s | 6.32 / 6.33 s | `OWN_PB=0x8` 6.55 / 6.55 |
  | 128 | 6.73 / 6.73 | 5.89 / 5.89 | |
  | 256 | 6.65 / 6.65 | **5.68 / 5.68** (588 tok/s) | `OWN_PB=0x16` (no bit 8) 5.71 / 5.71 |

  Best: blocks of 256 with `OWN_PB=1` (was 6.73 s at blocks of 64: -16 %). Bit 8 stays.
- **wa-2 wins everywhere it ran**: code 140.04 / 141.05 -> 141.66 / 141.21 tok/s, analysis 155.28 / 156.39 -> 156.75 /
  156.64, after a 3K prompt (with G128) 138.74 -> 144.41 (+4.1 %), prose (with G128) 117.97 -> 118.89. wa-1: code
  141.33 / 140.83, analysis 156.09 / 156.29. Checks of 2-6 tokens 0.15-0.37 ms cheaper (code).
- **The draft's candidate vocabulary** (`OWN_DR_VOCAB`, draft-only): code 141.61 / 142.19, analysis 158.07 / 157.94,
  prose 118.41 (+0.4-1.4 %); same answers, two fewer kept guesses on code (draft-only change).
- **G128 alone**: plain 101.65 / 98.71 against 100.95 / 101.48: neutral within noise; its xperm-2 partner is tp101.
- **Plain writing unchanged**: 100.95 / 101.48 tok/s.
- **One guess-log difference**: in code_w2_2, round 66, the draft's first confidence was 0.9049 against 0.9759 in all 19
  other runs of that prompt (tg98b, tg99c, tg100, every arm, including code_w2_1 and both runs with everything on).
  Same guesses, same kept count, same text; columns 2-5 identical. A rare run-to-run difference on the draft side
  (suspect: the draft's first position reads a buffer before it is final, e.g. `OWN_DR_NOWAIT`). tg101 repeats the
  code prompt to measure how often it happens.

## Check cost by guesses (median ms; `check-cost-by-guesses.txt`)

| run | 0 (1) | 1 (2) | 2 (3) | 3 (4) | 4 (5) | 5 (6) |
|---|---|---|---|---|---|---|
| code, d100 | 10.36 | 13.07 | 15.57 | 17.24 | 19.82 | 22.12 |
| code, wa-2 | 10.29 | 12.92 | 15.25 | 16.95 | 19.45 | 21.77 |
| analysis, d100 | 10.40 | 13.12 | 15.59 | 17.13 | 20.05 | 21.57 |
| analysis, wa-2 | 10.43 | 13.09 | 15.49 | 17.11 | 19.85 | 21.56 |
| after 3K, d100 | 10.98 | 14.07 | 16.46 | 18.46 | 21.44 | 23.18 |
| after 3K, G128 + wa-2 | 11.00 | 13.89 | 16.30 | 18.48 | 21.14 | 22.95 |

## xov2: exchanges beside compute (pb256 helper's six-card check, `xov2/`)

One layer's real launch order of two half-blocks with the eight pulls on a second in-order queue per card, each pull in
the register mode of the compute beside it, 16 work-groups ("E16"), every gathered row checked: 0 wrong values, 0
timeouts. Hidden share of the one-queue pull time: **91.3 % at 128-token halves, 90.7 % at 64** (per site at 128:
output-a 88.1 %, output-b 91.5 %, expert act 95.1 %, FFN rows 91.4 %). Today's pull form on a second queue hides only
43.5 %, matched modes at 64 groups 65.4 %: both design choices matter. Busy loops stood in for real kernels; pair swaps,
per-half engine state and real card skew are left to the engine gate. Predicted: 3K read at blocks of 256 with pb-1
5.68 s -> ~5.0 s. Design: `xov2/README-overlap.txt`. Engine patch (`OWN_PX`, opt-in) being written.

## Files

`tg100-summary.txt`, `spec/` (every guessing log), `check-cost-by-guesses.txt`, `xov2/` (summary, overlap design,
pb-1 README). Scripts in `../round18-scripts/strategy/` (build100.sh, build100-go.sh, tg100.sh).
