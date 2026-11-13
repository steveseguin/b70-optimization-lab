# Round 19, gate tg110 (build tp110 = sources 787729bcf, 2026-11-13 10:28-11:42)

tp110 = tp109 + `OWN_RUX5` default on (e004ace38) + qkv-1 (`OWN_QKV_SPLIT` default on: the q_a + kv rows split by card,
one gather per layer; helper `round19-qkv/`). Speed only from unprofiled runs, alternated, no sampler. The gate shared
the cards with helper runs (gaps of 200 s between sections).

## In plain words

- **Every trace identical, every answer the same, no fault**: prompt-1 traces with the new defaults at blocks 1-6, 16,
  64, 256 and with the split off at 1 / 4 / 64; 3K traces at px-512 and 256; 4 of 4 guessing runs SAME AS the plain
  run with guess logs equal to tg105v's; 3K (256 answers) x2 and 10K (64) the same as the references.
- **Plain**: a (tp109 + RUX5 = tp110 without the split) 108.82 / 109.34 tok/s, b (tp110) **111.63 / 111.10**.
- **Guessing**: code **157.29 / 158.10** (tg109 + RUX5: 155.10 / 155.15), analysis **174.84 / 175.98** (173.53 / 173.37).
- **Reads**: 3K 4.83 / 4.88 s (prompt halves do not take the split), 10K 15.74 s; decode after the 3K prompt 100.75 /
  100.56 tok/s, after 10K 98.08.

## Decision

tp110 is the new base (`dsv41-work/own_run_v41_tp110`).

## Files

`tg110-summary.txt`, `marks.txt`, `spec/` (guess logs). Scripts in `../round18-scripts/strategy/` (tg110.sh, build110*.sh).
