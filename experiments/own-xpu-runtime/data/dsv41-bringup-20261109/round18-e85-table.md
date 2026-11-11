| run | prompt tokens | reading tok/s | answer tok/s | ms per step (plain) | draft + check ms | disk MiB in answers | checks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| h16 |  |  | 63.79 | 15.68 |  | 6.9 | TRACE_IDENTICAL, IDS40_SAME |
| h5 |  |  | 63.11 | 15.85 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| h1 |  |  | 65.74 | 15.21 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| p1 |  |  | 74.55 | 13.41 |  | 15.9 | SPEED128_SAME |
| x34k_check | 33,815 | 273.3 | 59.93 | 16.69 |  | 7.7 | ANSWER64_SAME |
| x34k_cand | 33,815 | 273.2 | 67.11 | 14.90 |  | 23.5 | ANSWER256_SAME |
| x69k_cand | 68,506 | 266.9 | 64.70 | 15.46 |  | 24.4 | ANSWER256_SAME |
| x95k_cand | 95,497 | 262.2 | 63.00 | 15.87 |  | 24.4 | ANSWER256_SAME |
| x34k_cspec | 33,815 | 272.0 | 95.56 (guessing) |  | 2.32 + 20.89 | 37.7 | SAME AS the plain run |
| x69k_cspec | 68,506 | 265.5 | 86.67 (guessing) |  | 2.30 + 21.24 | 16.0 | SAME AS the plain run |
