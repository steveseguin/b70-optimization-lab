# pc200: tp111 speed with every card capped at 200 W (owner's reset test, 2026-11-13 20:45-21:25)

Owner, 20:35: "you can try to lower the power on all the GPUs, and see if that helps. maybe 175w limit? ... or 200w
even". All six cards' xe hwmon `power1_cap` set to 200 W at 20:44:12 (was 275 W on 03 / 83, 230 W on the other four;
`powercap-20261113.txt`). Same binary (tp111), same commands and references as tg111 (uncapped, 2026-11-13 morning).
Unprofiled, no sampler. Every answer the same as the references; no fault or corrected-error line in the kernel log.

| run | uncapped (tg111, tp111) | 200 W (pc200) | change |
|---|---|---|---|
| plain answers (128) | 110.90 / 111.01 tok/s | 110.18 / 107.92 | -1 .. -3 % |
| guessing, code | 157.54 | 152.62 | -3.1 % |
| guessing, analysis | 174.93 | 169.46 | -3.1 % |
| 3K read | 4.78 / 4.89 s | 5.33 / 5.31 s | +10 % time (-11 % tok/s) |
| answers after the 3K read | 99.15 / 100.09 tok/s | 99.29 / 100.68 | same |
| 10K read | 15.09 s | 17.06 s | +13 % time |
| answers after the 10K read | 96.87 tok/s | 94.73 | -2 % |

In plain words: writing answers barely notices the cap (it waits on memory, not on arithmetic); reading prompts does
(10-13 % slower), because the prompt kernels are arithmetic-heavy and the cards slow their clocks at the lower power.
This matches the uncapped profile (round19-tlp109 px512): the two 275 W cards ran the same prompt kernels ~10 % faster
than the 230 W cards (card 0 experts 328 vs card 2 364 ms per piece, dense rows 222 vs 248; card 0 then waits 82 ms in
exchanges). So power is a real lever for prompt reading; raising the four 230 W cards to 275 W (their peak limit is
460 W) would likely cut the read time by up to ~10 %, but that needs the owner's decision and the reset question first.

Files: `summary.txt` (the run log), `powercap-20261113.txt` (cap log). Scripts: `../round18-scripts/strategy/pc200.sh`,
`powercap.sh` (re-applies 175 / 200 W after a boot while the test runs).
