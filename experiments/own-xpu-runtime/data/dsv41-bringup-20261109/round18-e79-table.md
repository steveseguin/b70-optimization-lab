# e79 (tp66): attention heads split by units of 4 (OWN_TP_HEADS), round18-scripts/e79.sh
# n = whole groups (8c/6: 8,8,16,8,8,16 heads), a = A 3,3,3,3,2,2 (12,12,12,12,8,8 heads; pairs 0-1, 2-3), ad = A + the draft's stages (OWN_TP_HEADS_DR=1), bd = B 2,3,3,3,3,2 + draft
# gates: traces of blocks of 16 / 5 / one token byte-identical (A; B and n at 16), plain 128-token answers identical; 48 of 48 guessing answers SAME as the plain run; every arm keeps exactly n's guesses (the draft's values unchanged)

| run | code | prose | analysis | ops | docs | median of 5 | 3K document | check ms (mean of 6) | engram rows us/step | MiB from disk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n1 | 101.38 | 84.98 | 114.94 | 101.77 | 105.14 | 101.77 | 110.30 | 18.92 | 456 | 423.4 |
| a1 | 100.86 | 84.19 | 114.24 | 101.50 | 103.94 | 101.50 | 109.42 | 19.08 | 427 | 48.5 |
| ad1 | 100.28 | 83.66 | 113.82 | 100.95 | 103.92 | 100.95 | 109.30 | 19.12 | 448 | 90.1 |
| bd1 | 100.56 | 84.12 | 114.09 | 101.16 | 104.04 | 101.16 | 109.14 | 19.08 | 428 | 130.1 |
| bd2 | 100.29 | 84.07 | 113.95 | 100.98 | 103.60 | 100.98 | 108.97 | 19.12 | 442 | 389.0 |
| ad2 | 100.50 | 84.08 | 113.84 | 100.99 | 104.24 | 100.99 | 109.51 | 19.08 | 408 | 0.0 |
| a2 | 100.72 | 84.28 | 113.99 | 101.43 | 104.62 | 101.43 | 109.44 | 19.07 | 410 | 0.0 |
| n2 | 101.54 | 85.14 | 114.94 | 101.80 | 105.41 | 101.80 | 110.43 | 18.90 | 408 | 0.0 |

3K document read in blocks of 16 (tok/s, the same runs):

| arm | round 1 | round 2 |
| --- | --- | --- |
| n | 277.7 | 276.4 |
| a | 288.6 | 288.1 |
| ad | 288.2 | 288.8 |
| bd | 288.4 | 288.5 |

Plain 128-token answers (tok/s): whole groups 77.84, 77.99; A 77.56 (and 74.85 with 11.2 MiB of engram rows read from disk), first run of the build 77.36 (A + draft flag); A with pulls from 6 KB (OWN_XPULL_MIN=6144) 76.11, 76.91.
