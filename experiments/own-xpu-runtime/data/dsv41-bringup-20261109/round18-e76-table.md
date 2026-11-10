| 3K document, blocks of 16 (tp64) | round 1 tok/s | round 2 tok/s |
| --- | --- | --- |
| default (token groups of 4) | 277.0 | 277.0 |
| + OWN_MT_TGR=16:4, rows >= 4096 | 273.5 | 273.1 |
| + OWN_MT_TGR=16:4, rows >= 2048 | 269.7 | 269.6 |
| + OWN_MT_TGR=16:4, all matrices | 231.3 | 231.2 |
| + OWN_MT_TGR=16:2, rows >= 4096 | 277.9 | 279.0 |
| OWN_MT_TGM=16:3 + OWN_MT_TGR=16:4 | 267.2 | 267.4 |
| OWN_MT_TGU=3 | 276.4 | 276.4 |
| OWN_MT_TGU=0 | 276.6 | 276.7 |

| new long document (never run) | tokens | cold tok/s | warm tok/s | cold / warm |
| --- | --- | --- | --- | --- |
| L1 | 2686 | 275.0 | 276.4 | 0.995 |
| L2 | 3118 | 274.4 | 276.0 | 0.994 |
| L3 | 2604 | 276.7 | 278.2 | 0.995 |
| L4 | 2766 | 273.6 | 275.0 | 0.995 |
