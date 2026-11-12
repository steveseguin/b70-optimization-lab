# Round 19, gate tg101 (build tp101, 2026-11-11)

tp101 = tp100 + xperm-2 compiled in (`-DOWN_R2_TAB_COPY=1`: the IQ2_S / IQ2_XS / IQ1_S routed kernels copy their
grid tables from a constant image instead of computing them per work-group). Build 21:20-21:39; gate 21:39-22:07
(ALLDONE). A = tp100, B = tp101, alternated. Settings carried from tg100: `OWN_PB=1` at prompt blocks of 256,
`OWN_ATT_WA=2`, `OWN_PAIR_G128=1` (G128) where named.

## In plain words

- **Every trace identical** (14 prompt-1 traces with defaults, G128, pb-1 at 256, wa-2, everything together; 3K traces
  at 64 and with everything at 256). All 18 guessing runs gave the same text as plain writing; all 10 code /
  analysis guess logs equal to tg100's wa-2 logs (the tg100 draft-confidence difference did not come back).
- **Plain writing +1.5 % (+2.4 % with G128)**: tp100 101.62 / 101.58 tok/s, with G128 101.32 / 101.42; tp101 103.12 /
  102.93, with G128 **103.76 / 103.92**. G128 pays only together with xperm-2.
- **Guessing** (wa-2 + G128): code A 140.49 / 141.32 / 141.70 vs B 139.98 / 143.09 / 142.68 (+0.5 % mean), analysis
  155.67 / 156.51 vs 154.86 / 157.05 (same), prose 118.34 -> 120.47 (+1.8 %), after a 3K prompt 143.25 -> 145.35
  (+1.5 %). With the draft's candidate vocabulary: code 141.88 -> **143.75**, analysis 157.88 -> **160.17** tok/s.
- **3K read at 256 with pb-1**: 5.68 / 5.68 s both builds (tp101's first run 5.76 with a slower first step).

## Check cost by guesses (median ms, round 2; `check-cost-by-guesses.txt`)

| run | 0 (1) | 1 (2) | 2 (3) | 3 (4) | 4 (5) | 5 (6) |
|---|---|---|---|---|---|---|
| code, tp100 | 10.30 | 12.97 | 15.35 | 17.09 | 19.57 | 21.79 |
| code, tp101 | 10.08 | 12.76 | 15.16 | 16.85 | 19.47 | 21.67 |
| analysis, tp100 | 10.35 | 13.14 | 15.43 | 17.20 | 19.81 | 21.57 |
| analysis, tp101 | 10.16 | 12.92 | 15.36 | 16.94 | 19.65 | 21.27 |

## Also this round

- 21:24:59 card 5 software fault from a helper's one-card bench (use-after-free of host table vectors in the bench, not
  the engine); evidence `dsv41-work/faults/fault-20261111T2124/`; tg101 ran clean on all six cards afterwards; the health
  probe runs after the gate.

## Files

`tg101-summary.txt`, `spec/`, `check-cost-by-guesses.txt`. Scripts in `../round18-scripts/strategy/` (build101.sh,
build101-go.sh, tg101.sh).
