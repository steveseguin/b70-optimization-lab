# e77: tp65 (large register file where a kernel would spill + OWN_ENG_AHEAD) against tp64; n = tp65, a = tp64, w0 = tp65 first runs

| run | code | prose | analysis | ops | docs | median of 5 | 3K document | check ms (mean of 6) | engram rows us/step | MiB from disk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| w0 | 101.50 | 84.98 | 115.11 | 101.90 | 105.03 | 101.90 | 110.20 | 18.92 | 413 | 0.0 |
| a1 | 98.54 | 82.35 | 111.63 | 99.23 | 102.09 | 99.23 | 106.84 | 19.26 | 419 | 0.0 |
| n1 | 101.44 | 84.84 | 114.71 | 102.06 | 105.22 | 102.06 | 109.98 | 18.93 | 412 | 0.0 |
| n2 | 101.43 | 85.09 | 114.92 | 102.08 | 104.87 | 102.08 | 110.33 | 18.92 | 411 | 0.0 |
| a2 | 98.68 | 82.17 | 111.69 | 99.17 | 102.08 | 99.17 | 106.70 | 19.27 | 418 | 0.0 |

| new long document (never run), tp65 | OWN_ENG_AHEAD | tokens | cold tok/s | warm tok/s | cold / warm |
| --- | --- | --- | --- | --- | --- |
| L5 | 0 (off) | 3213 | 273.7 | 275.2 | 0.995 |
| L6 | 16 (default) | 3219 | 273.6 | 273.5 | 1.000 |
| L7 | 0 (off) | 2568 | 274.8 | 276.3 | 0.995 |
| L8 | 16 (default) | 2246 | 275.7 | 275.0 | 1.003 |
