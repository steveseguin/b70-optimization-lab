# e81 (tp67): the split attention layout only for blocks of >= 16 tokens (OWN_TP_HEADS + OWN_TP_HEADS_MIN=16, every card holds both layouts' rows), round18-scripts/e81.sh
# n = default (whole groups), d = A 3,3,3,3,2,2 + MIN=16; gates: traces of blocks of 16 / 5 / one token byte-identical (d; n at 16), plain 128-token answers identical (78.29-78.30 tok/s both); 24 of 24 guessing answers SAME as the plain run, guesses kept identical

| run | code | prose | analysis | ops | docs | median of 5 | 3K document | check ms (mean of 6) | engram rows us/step | MiB from disk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n1 | 101.09 | 84.73 | 114.76 | 101.82 | 105.19 | 101.82 | 110.16 | 18.95 | 463 | 212.5 |
| d1 | 101.44 | 85.07 | 114.90 | 102.09 | 105.18 | 102.09 | 109.91 | 18.92 | 409 | 0.0 |
| d2 | 101.17 | 85.03 | 115.09 | 102.02 | 105.10 | 102.02 | 110.59 | 18.90 | 409 | 0.0 |
| n2 | 101.71 | 85.06 | 114.90 | 102.30 | 105.27 | 102.30 | 110.21 | 18.89 | 406 | 0.0 |

3K document read in blocks of 16, 16 answer tokens each (all the same as the plain answer), tok/s:

| arm | round 1 | round 2 |
| --- | --- | --- |
| b | 278.0 | 278.0 |
| dA | 290.2 | 290.1 |
| dB | 289.6 | 289.8 |
| r4 | 281.0 | 281.1 |
| dr | 292.9 | 292.8 |

b = default, dA / dB = A / B (2,3,3,3,3,2) + MIN=16, r4 = OWN_MT_TGR=16:4 OWN_MT_TGR_ROWS=4096, dr = dA + r4
