# tg112: tp112 gate (2026-11-13 21:10-22:40, every card capped at 200 W)

tp112 = tp111 + rux6-1 default on (`OWN_RUX6`, prompt-block routed-expert launches with x prefetches; lab 630371f1b).
Built by `build112.sh` (exit 0, 1,339 s). All runs under the owner's 200 W reset-test cap (round19-pc200), so the
speeds compare only with each other and with pc200, not with tg111.

- Gate 1 (prompt-1 traces h1 / h5 / h16 / h64 / h256, and h64 / h256 with OWN_RUX6=0, vs runs/ab1): identical.
- Gate 2 (3K traces at px-512 and blocks of 256 vs runs/gm64/t3k_ref): identical.
- Every answer the same as its reference (plain, guessing, 3K, 10K, 34K, 95K); guessing logs the same as tg105v.
- No fault or corrected-error line in the kernel log.

| run (200 W) | tp111 | tp112 |
|---|---|---|
| plain (128 answers) | 111.12 / 110.87 tok/s | 111.27 / 110.35 |
| guessing code / analysis | (pc200: 152.62 / 169.46) | 152.86 / 169.70 |
| 3K read | 5.26 / 5.32 s | 5.33 / 5.32 s |
| 10K read | 17.15 s | 17.14 s |
| 34K / 95K read | | 56.06 / 162.42 s (uncapped tp111: 48.6 / 140.7) |
| answers after 34K / 95K | | 96.40 / 90.51 tok/s (uncapped tp111: 98.3 / 91.5) |

In plain words: tp112 is exact and becomes the base. Its prompt change (-2 % uncapped, round19-rux6) does nothing
under the 200 W cap: the prompt kernels are then held by the power limit, and a kernel that waits less only draws
more power at a lower clock. While the cap is on, prompt levers must remove work (instructions, bytes, repeated
computation), not waiting.
