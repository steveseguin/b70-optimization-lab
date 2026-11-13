# qkv-1 speed A/B (qsp110, 2026-11-13 09:34-10:2x)

Binary `own_run_v41_qkv1` (lab 96ffc00a2 + qkv-1), `OWN_RUX5=1` in both arms; s0 = `OWN_QKV_SPLIT=0`, s1 = on (14).
Unprofiled, no sampler, alternated. Every answer the same (`qsp110-summary.txt`: SPEED128_SAME x5, 8 of 8 guessing runs
SAME AS the plain run and GLOG_SAME vs tg105v, 3K ANSWER256_SAME x2).

| run | split off | split on |
|---|---|---|
| plain (128 tokens) | 109.11 / 107.78 | 111.04 / 111.42 |
| guessing, code | 155.02 / 155.66 (check 12.92 / 12.85 ms) | 158.00 / 158.11 (12.65 / 12.64) |
| guessing, analysis | 172.76 / 173.22 (check 14.67 / 14.62) | 176.06 / 176.39 (14.37 / 14.34) |
| 3K read (px-512) | 4.81 s | 4.81 s (halves do not take the split) |
| decode after the 3K prompt | 98.74 | 101.83 |

Decision: default on from tp110 (sources 787729bcf). Helper ledger, design and traces: `README.md`, `traces-summary.txt`.
