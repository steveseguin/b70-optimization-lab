# Round 19, gate tg111 (build tp111 = sources 912ac0900, 2026-11-13 12:15-13:07)

tp111 = tp110 + idxsplit-1 (`OWN_IDX_SPLIT` default 1: in prompt reads each card computes the index lists of its own
sixth of the tokens and the lists are gathered on the copy engines; helper `round19-idxsplit/`). Speed only from
unprofiled runs, alternated, no sampler; the gate shared the cards with helper runs (200 s gaps).

## In plain words

- **Every trace identical, every answer the same, no fault**: prompt-1 traces with the new defaults at blocks 1, 5, 16,
  64, 256 and with the split off at 64 / 256; 3K traces at px-512 and 256; guessing code and analysis SAME AS the
  plain run with guess logs equal to tg105v's; 3K (256 answers) x4, 10K (64) x2, x34k and x95k (256 answers each, vs
  e82's plain answers) all the same.
- **Long documents (tp111)**: x34k read **48.62 s** (tp107/lc107b: 56.1), x95k **140.66 s** (helper control with the split
  off: 166.34 s; -15 %); decode after them 98.26 / 91.49 tok/s.
- **10K read**: 15.84 s (tp110) -> **15.09 s** (tp111). 3K: 4.78 / 4.85 s (tp110) vs 4.78 / 4.89 s (tp111): no change
  (little index work at 3K).
- Plain and guessing unchanged (the split is prompt-only): plain a (tp110) 111.41 / 111.46, b (tp111) 111.01 / 110.90;
  code 157.54, analysis 174.93 tok/s.

## Decision

tp111 is the new base (`dsv41-work/own_run_v41_tp111`).

## Files

`tg111-summary.txt`, `marks.txt`, `spec/`. Scripts in `../round18-scripts/strategy/` (tg111.sh, build111*.sh; hsw111.sh =
the queued head-placement A/B, not run yet at 13:20).
