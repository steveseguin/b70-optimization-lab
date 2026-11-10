# e78 (tp65): one screening round of the guessing block settings tuned before the large register file (round18-scripts/e78.sh)
# n = current (BEST), r2 = 2-row blocks for checks, rr = row blocks from 2,048 rows, g4 = one token group for blocks of 4, g6 = groups of 2 for blocks of 6; every answer SAME as the plain run (30 of 30)

| run | code | prose | analysis | ops | docs | median of 5 | 3K document | check ms (mean of 6) | engram rows us/step | MiB from disk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n | 101.49 | 85.10 | 115.05 | 101.85 | 105.34 | 101.85 | 110.29 | 18.91 | 412 | 0.0 |
| r2 | 100.68 | 84.27 | 113.99 | 101.25 | 104.43 | 101.25 | 109.65 | 19.05 | 416 | 0.0 |
| rr | 100.63 | 84.54 | 113.89 | 101.46 | 104.49 | 101.46 | 109.16 | 19.05 | 415 | 0.0 |
| g4 | 101.40 | 84.92 | 114.68 | 102.09 | 105.22 | 102.09 | 110.04 | 18.93 | 413 | 0.0 |
| g6 | 101.35 | 84.86 | 113.85 | 101.73 | 104.55 | 101.73 | 109.73 | 19.01 | 414 | 0.0 |

3K document read in blocks of 16 (16 answer tokens each, all the same as the plain answer):

| setting | tok/s |
| --- | --- |
| b | 277.7 |
| r2 | 280.2 |
| r4 | 281.1 |
| m9 | 257.0 |

b = default (token groups of 4), r2 / r4 = row blocks of 2 / 4 for matrices of >= 4,096 rows (OWN_MT_TGR=16:2 / 16:4, OWN_MT_TGR_ROWS=4096), m9 = OWN_MT_TGM=16:9
