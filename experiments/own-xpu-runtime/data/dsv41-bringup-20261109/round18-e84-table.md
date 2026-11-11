| run | prompt tokens | reading tok/s | answer tok/s | ms per step (plain) | draft + check ms | disk MiB in answers | checks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| h16 |  |  | 64.49 | 15.51 |  | 6.9 | TRACE_IDENTICAL, IDS40_SAME |
| h5 |  |  | 66.07 | 15.14 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| h1 |  |  | 65.70 | 15.22 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| p1 |  |  | 74.66 | 13.39 |  | 15.9 | SPEED128_SAME |
| x34k_check |  |  | 59.75 | 16.74 |  | 7.7 | ANSWER64_SAME |
| x19k_cand | 18,692 | 278.7 | 67.99 | 14.71 |  | 30.5 | ANSWER256_SAME |
| x34k_cand | 33,815 | 271.0 | 67.23 | 14.87 |  | 20.3 | ANSWER256_SAME |
| x69k_plain | 68,506 | 257.4 | 60.14 | 16.63 |  | 23.0 | ANSWER256_SAME |
| x69k_cand | 68,506 | 257.0 | 66.02 | 15.15 |  | 0.1 | ANSWER256_SAME |
| x95k_cand | 95,497 | 246.6 | 62.92 | 15.89 |  | 38.9 | ANSWER256_SAME |
