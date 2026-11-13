# Round 19, gate tg109 (build tp109, 2026-11-13 03:29-03:49)

tp109 = tp108 with `OWN_XPUSH2` (classes 0x0F) and `OWN_RUX4` as defaults + rux5-1 (`OWN_RUX5`, opt-in: the one-token
and 2-6-token check routed-expert launches on rux4's gathers-first forms; helper `round19-rux5/`). Speed only from
unprofiled runs alternated, no sampler. Timelines at the end for the next budget.

## In plain words

- **Every trace identical, every answer the same, no fault.** 16 traces (defaults at blocks 1-6, 16, 64, 256; RUX5 at
  1-6 and 64), 3K traces at px-512 and 256, 8 of 8 guessing runs SAME AS the plain run, every guess log equal to tg105v's.
- **tp109 defaults = tp108 + `OWN_XPUSH2=1 OWN_RUX4=1`, as expected**: plain a (tp108 + XP + RX) 109.02 / 109.27, b (tp109)
  109.25 / 109.27 tok/s; 3K read 4.85 / 4.81 s (692 tok/s), 10K 15.68 s (678 tok/s).
- **RUX5: guessing +2-3 %, plain unchanged.** Plain c 109.68 / 109.08. Code 151.97 / 152.29 -> **155.10 / 155.15**
  (check 13.2 -> 12.9 ms per cycle); analysis 168.59 / 169.51 -> **173.53 / 173.37** (check 15.05 -> 14.6 ms). The
  helper predicted -0.31 to -0.73 ms per check of 2-6 tokens and -0.05 ms per one-token step; measured checks of 1-5
  guesses -0.26 / -0.52 / -0.65 / -0.81 / -0.52 ms (code, medians).

## Decision

`OWN_RUX5` default on in the tp110 sources (`OWN_RUX5=0` restores the tp109 forms).

## Check cost by guesses checked (unprofiled, median ms; `check-cost-by-guesses.txt`)

| run | 0 | 1 | 2 | 3 | 4 | 5 | draft |
|---|---|---|---|---|---|---|---|
| code, tp109 | 9.63 | 11.88 | 14.03 | 15.89 | 18.29 | 20.43 | 1.73 |
| code, + RUX5 | 9.59 | 11.62 | 13.51 | 15.24 | 17.48 | 19.91 | 1.74 |
| analysis, + RUX5 | 9.64 | 11.71 | 13.71 | 15.32 | 17.68 | 19.62 | 1.76 |

(tg103: 10.10 / 12.73 / 15.16 / 16.57 / 19.01 / 21.29, draft ~1.9.) The empty check is now 0.45 ms over a plain step;
each further guess costs ~2.0 ms.

## Budgets for the next step (timelines, RUX5 on; per-kernel times valid, overlap not)

One-token step (`one-token-budget.txt`, 8 steps): busy 8.83 ms on every card, 853 launches.

| part | card 2 (16 heads) | card 0 (8 heads) |
|---|---|---|
| dense rows (+ riders: hc finish, rope, norm + mix dots + router, shared down comb) | 4.64 | 4.01 |
| routed experts (RoutedUQ 76 x 23.6 us + grouping etc.) | 1.92 | 1.86 |
| exchanges (XchgP 120 x 7.9 us, XchgQ 40 x 8.5 us) | 1.33 | 2.00 |
| norms + mix | 0.48 | 0.48 |
| attention + indexer | 0.38 | 0.40 |
| small | 0.09 | 0.09 |

Reading: card 2 reads 2.51 GB per step, ~2.1 GB of it dense rows (3.8 ms at 550 GB/s), so its dense rows already run at
~82 % of the bytes floor: the lever there is reading less (the replicated q_a + kv rows, 332 MB per card: helper qkv;
router 157 MB; hc fn 151 MB) and the 16-head imbalance (0.63 ms; the light cards wait 0.67 ms more in exchanges). The
experts run ~1.9 ms against a bytes floor of 0.74 and an issue floor of ~1.1 (decode instructions per weight). The 160
exchanges cost ~8 us each on the last card to arrive (transport + launch): folding pushes into their producers is the
remaining exchange lever.

Checks by tokens (`ck-by-m-parts-card2.txt`, `ck-by-m-card{2,0}.txt`; code prompt, checks 20-119, timeline busy ms):

| part (card 2) | M=1 | M=2 | M=3 | M=4 | M=5 | M=6 | per token M2->5 |
|---|---|---|---|---|---|---|---|
| dense rows | 3.74 | 4.04 | 4.51 | 4.78 | 5.61 | 5.76 | 0.52 |
| experts + router | 2.27 | 3.46 | 4.35 | 5.14 | 5.90 | 7.10 | 0.81 |
| exchanges | 1.52 | 1.81 | 2.16 | 2.77 | 3.31 | 4.09 | 0.50 |
| attention | 0.54 | 0.51 | 0.59 | 0.58 | 0.72 | 0.44 | |
| norms + mix | 1.00 | 0.98 | 1.13 | 0.75 | 0.90 | 0.79 | |
| total | 9.30 | 11.05 | 13.03 | 14.54 | 16.72 | 19.10 | 1.89 |

(the categories differ from tl105's: router rows and FlNormK count here as dense rows / norms; compare within this
table.) The extra token's experts (0.81 ms) sit near their bytes (409 MB per card per token = 0.74 ms); dense rows and
exchanges (~0.5 each) are the parts of the slope that are not bytes.

## Files

`tg109-summary.txt`, `marks.txt`, `spec/` (guess logs), `check-cost-by-guesses.txt`, `one-token-budget.txt`,
`ck-by-m-card{0,2}.txt`, `ck-by-m-parts-card{0,2}.txt`, `tools/` (bym_cat.py: parts by M from dsv41_ck_by_m.py output;
one_budget.py: one-token parts per card from an OWN_TIMELINE file). Timelines (66 MB / 4.6 MB) kept out of git:
`dsv41-work/runs/tg109/{tl_ck,tl_one}.txt`. Scripts in `../round18-scripts/strategy/` (build109*.sh, tg109.sh).
