# Round 19, gates tg99 + tg99b + tg99c (build tp99, 2026-11-11)

tp99 = tp98 + dride default (checks of 4-6 tokens) + wa-1 v3 (`OWN_ATT_WA=1`: WindowAppendM inside the check
attention launch, 2-8 tokens) + xll-1 (`OWN_XLL`: pull exchanges in one PCIe round trip), the last two opt-in.
Build 16:49-17:07 (1054 s). The gate ran in three parts because the host failed twice:

- tg99 17:07-17:17: traces until the fifth host reset (~17:17:24, ~3 s into run h5xa's start).
- tg99b 17:55-17:59: the rest of the traces, then the host froze (~17:59:40) during t3k_b64xa (3K read with
  `OWN_XLL=1`); the owner power-cycled it at 19:18.
- tg99c 19:34-19:47:39 (ALLDONE): everything else, without `OWN_XLL` (banned after the freeze: the last three host
  events, 15:17 / 17:17 / 17:59, all coincided with one-trip-pull traffic).

## In plain words

- **Every trace is identical:** the defaults at blocks of 1, 4, 5, 6 and 64 tokens and dride switched off at 5;
  all 11 `OWN_ATT_WA=1` arms (blocks 2, 3, 4, 5, 6, 8, 16, 64; `OWN_ATT_F=0` at 2 and 5; `OWN_TP_HEADS_MIN=3` at 5);
  `OWN_XLL=1` at 1, 4, 5, 6, 64 and with `OWN_XLL_QUICK=3` at 1 and 5; all three together at 5; the 3K traces
  default and WA. 12 / 12 guessing runs the same as plain, every guess log equal (d99 = tg98b's dride run).
- **Speeds hold:** plain 100.94 / 101.56 tok/s; 3K read 6.78 / 6.79 s (blocks of 256: 6.71 s); guessing code
  139.75 / 138.12, analysis 154.53 / 155.66 (tg98b with dride by hand: 140.65 / 140.76, 156.04 / 155.86).
- **wa-1 (`OWN_ATT_WA=1`) is mixed at short context and wins after a long prompt:** code 140.35 / 140.66 (+1 %),
  analysis 152.12 / 156.20 (-0.9 % / +0.3 %), prose 118.08 -> 118.47, guessing after a 3K prompt 138.14 -> 143.22
  (+3.7 %). Matches the helper's card-3 bench (wins at 2-4 tokens and long context, loses at 6-token checks at short
  context and at 384 slots); wa-2 (a per-shape rule) is being written.
- **xll-1 was never timed** (its speed arms were dropped with the ban); its traces were all identical.

## Check cost by guesses (median ms; `check-cost-by-guesses.txt`)

| run | 0 (1) | 1 (2) | 2 (3) | 3 (4) | 4 (5) | 5 (6) |
|---|---|---|---|---|---|---|
| code, d99 | 10.33 | 13.08 | 15.51 | 17.33 | 19.80 | 22.15 |
| code, WA | 10.37 | 13.03 | 15.45 | 17.20 | 19.92 | 22.02 |
| after 3K, d99 | 10.96 | 14.07 | 16.66 | 18.61 | 21.59 | 23.29 |
| after 3K, WA | 11.02 | 13.94 | 16.31 | 18.40 | 21.27 | 22.98 |

## Files

`tg99-summary.txt`, `tg99b-summary.txt`, `tg99c-summary.txt`, `spec/` (tg99c spec logs),
`check-cost-by-guesses.txt`, `host-reset-20261111T1717/` (BERT, telemetry, probe, the I210 setpci before / after),
`freeze-20261111T1759/` (gate summary and telemetry at the freeze, probe after the power cycle). Scripts in
`../round18-scripts/strategy/` (build99.sh, tg99.sh, tg99b.sh, tg99c.sh).
