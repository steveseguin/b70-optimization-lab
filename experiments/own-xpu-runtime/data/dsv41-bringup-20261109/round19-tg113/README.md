# tg113: tp113 (prt-1 + rux7-1 defaults) gated exact; prompt reading -8 % at default power

tp113 = tp112 + prt-1 (`OWN_PRT` default 3: the prompt router and the PX halves' q_a + kv rows split across the cards by
tokens, gathered, the same bits) + rux7-1 (`OWN_RUX7` default 1: layer 0's Q2_K routed down in a grouped form).
Sources 543b796ca, binary `dsv41-work/own_run_v41_tp113`. Three passes because of two host resets:

- tg113 (2026-11-14 01:20-02:03, 200 W cap): gate 1 (prompt-1 traces at 1 / 5 / 16 / 64 / 256, defaults and
  `OWN_PRT=0 OWN_RUX7=0`) identical; 3K traces b512 / b256 identical; cut by the 02:03 host reset during t3k_c1.
- tg113b (10:28, 175 W cap): t3k_c1 identical; cut by the ~10:29 reset at the start of t3k_c2.
- tg113c (11:08-12:20, cap test over, default power: 230 W, 275 W on cards 0 / 3): the rest. Every trace identical,
  every answer the same as its reference (3K vs e52, 10K vs tg107, x34k / x95k vs e82, guessing GLOG vs tg105v).

| run (default power, unprofiled, alternated) | tp112 | tp113 |
|---|---|---|
| plain (128 answers) | 111.34 / 111.72 tok/s | 111.63 / 111.68 |
| 3K read | 4.73 / 4.74 s | 4.47 / 4.30 s |
| 10K read | 14.95 s | 13.66 s |
| x34k read / answers | (tg111, tp111: 48.6 s) | 44.19 s / 97.17 tok/s |
| x95k read / answers | (tg111, tp111: 140.7 s) | 127.72 s / 91.32 tok/s |
| guessing code / analysis | | 156.90 / 174.97 tok/s |

Prompt-work weights for the two 275 W cards (U1 `OWN_PRT_W=4,2,2,4,2,2`, U2 `5,2,2,5,1,1`): 3K 4.31-4.35 s, 10K 13.68,
x34k 44.34, x95k 127.75 - no gain over the defaults; closed. In plain words: the two prompt changes make prompt reading
about 8 % faster with the same answers; tp113 is the base for tp114.

Files: `summary-tg113*.txt`. Scripts: `../round18-scripts/strategy/tg113*.sh`, `build113*.sh`.
