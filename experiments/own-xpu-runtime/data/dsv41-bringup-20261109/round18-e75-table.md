# e75 (tp64: EARLY + LATE + DEV on by default; n = default, s = OWN_TP_SPIN_US=2000, w0 = first runs after the build)

| run | code | prose | analysis | ops | docs | median of 5 | 3K document | check ms (mean of 6) | engram rows us/step | MiB from disk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w0 | 98.55 | 82.23 | 111.57 | 98.74 | 102.01 | 98.74 | 106.98 | 19.28 | 441 | 423.3 |
| n1 | 98.38 | 82.51 | 111.66 | 99.17 | 102.37 | 99.17 | 107.06 | 19.24 | 415 | 0.0 |
| s1 | 98.65 | 82.55 | 111.71 | 99.08 | 102.47 | 99.08 | 106.87 | 19.24 | 415 | 0.0 |
| s2 | 98.50 | 82.30 | 111.49 | 99.11 | 102.27 | 99.11 | 106.98 | 19.26 | 415 | 0.0 |
| n2 | 98.50 | 82.42 | 111.43 | 99.03 | 102.21 | 99.03 | 107.14 | 19.26 | 415 | 0.0 |

# fresh prompts f13-f24, each cold then warm (o = OWN_ENG_EARLY=0 OWN_ENG_LATE=0 OWN_ENG_DEV=0, n = default)

| prompt | setting | cold tok/s | warm tok/s | cold / warm | check ms cold | check ms warm | MiB from disk cold / warm | engram rows us cold / warm | cold = warm text |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| f13 | o | 102.57 | 105.01 | 0.977 | 20.92 | 20.37 | 91.5 / 0.0 | 794 / 400 | SAME |
| f14 | n | 103.12 | 102.70 | 1.004 | 19.07 | 19.14 | 92.8 / 0.0 | 424 / 421 | SAME |
| f15 | o | 80.43 | 82.92 | 0.970 | 17.94 | 17.32 | 100.0 / 0.0 | 761 / 273 | SAME |
| f16 | n | 79.90 | 80.10 | 0.998 | 17.48 | 17.44 | 100.7 / 0.0 | 387 / 371 | SAME |
| f17 | o | 80.35 | 82.49 | 0.974 | 18.64 | 18.08 | 104.8 / 0.0 | 758 / 301 | SAME |
| f18 | n | 97.66 | 97.92 | 0.997 | 18.43 | 18.39 | 88.9 / 0.0 | 415 / 398 | SAME |
| f19 | o | 83.11 | 85.40 | 0.973 | 18.02 | 17.46 | 101.7 / 0.0 | 738 / 281 | SAME |
| f20 | n | 95.70 | 95.96 | 0.997 | 19.95 | 19.89 | 101.9 / 0.0 | 457 / 436 | SAME |
| f21 | o | 88.13 | 90.46 | 0.974 | 19.00 | 18.44 | 96.0 / 0.0 | 782 / 325 | SAME |
| f22 | n | 91.72 | 91.85 | 0.999 | 17.62 | 17.60 | 90.8 / 0.0 | 389 / 379 | SAME |
| f23 | o | 80.55 | 82.84 | 0.972 | 18.18 | 17.61 | 96.1 / 0.0 | 736 / 275 | SAME |
| f24 | n | 91.54 | 91.32 | 1.002 | 18.33 | 18.38 | 89.4 / 0.0 | 413 / 401 | SAME |
setting o: 6 prompts, cold / warm tok/s median 0.974, check +0.56 ms per round (median)
setting n: 6 prompts, cold / warm tok/s median 0.998, check +0.03 ms per round (median)
