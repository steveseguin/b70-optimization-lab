| run | prompt tokens | reading tok/s | answer tok/s | ms per step (plain) | draft + check ms | disk MiB in answers | checks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ref_t1 | 36 | 75.2 | 64.49 | 15.51 |  | 6.9 |  |
| ref_def | 36 | 32.0 | 31.35 | 31.90 |  | 0.0 | ANSWER40_SAME |
| ref_t1-vs-f32-six-card-greedy-ids-40.txt |  |  |  |  |  |  | ANSWER40_SAME |
| ref_t1-vs-six-card-greedy-ids-100.txt |  |  |  |  |  |  | ANSWER40_DIFFERS |
| ref_t1-vs-cards-only-p1-greedy-ids.txt |  |  |  |  |  |  | ANSWER40_SAME |
| ref_t1-vs-cpu-reference-greedy-ids.txt |  |  |  |  |  |  | ANSWER40_DIFFERS |
| ref_speed | 36 | 245.8 | 74.78 | 13.37 |  | 15.9 |  |
| ref_code | 82 | 276.8 | 73.67 | 13.57 |  | 81.9 |  |
| ref_prose | 62 | 284.2 | 73.62 | 13.58 |  | 90.1 |  |
| ref_analysis | 113 | 282.5 | 73.57 | 13.59 |  | 62.1 |  |
| ref_ops | 74 | 285.7 | 73.46 | 13.61 |  | 84.4 |  |
| ref_docs | 78 | 288.5 | 73.76 | 13.56 |  | 72.3 |  |
| ref_p3k | 3,323 | 291.6 | 70.35 | 14.21 |  | 32.1 |  |
| ref_x19k | 18,692 | 279.4 | 68.00 | 14.71 |  | 28.8 |  |
| ref_x34k | 33,815 | 271.4 | 65.23 | 15.33 |  | 24.0 |  |
| ref_x69k | 68,506 | 257.3 | 60.43 | 16.55 |  | 30.4 |  |
| ref_x95k | 95,497 | 246.7 | 56.51 | 17.70 |  | 31.5 |  |
| h16 |  |  | 64.17 | 15.58 |  | 6.5 | TRACE_IDENTICAL, IDS40_SAME |
| h5 |  |  | 64.13 | 15.59 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| h1 |  |  | 66.61 | 15.01 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| h16a |  |  | 66.42 | 15.06 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| h5a |  |  | 67.12 | 14.90 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| h1a |  |  | 67.46 | 14.82 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| p1o1 |  |  | 74.64 | 13.40 |  | 14.6 | SPEED128_SAME |
| p1n1 |  |  | 75.72 | 13.21 |  | 0.0 | SPEED128_SAME |
| p1a1 |  |  | 78.26 | 12.78 |  | 0.0 | SPEED128_SAME |
| p1a2 |  |  | 78.13 | 12.80 |  | 0.0 | SPEED128_SAME |
| p1n2 |  |  | 76.36 | 13.10 |  | 0.0 | SPEED128_SAME |
| p1o2 |  |  | 76.31 | 13.10 |  | 0.0 | SPEED128_SAME |
| x34k_cchk | 33,815 | 273.9 | 61.07 | 16.37 |  | 3.4 | ANSWER64_SAME |
| p10k_rchk | 10,621 | 211.7 | 61.74 | 16.20 |  | 3.0 |  |
| code_n1 | 82 | 283.8 | 99.12 (guessing) |  | 2.30 + 18.07 | 88.8 | SAME AS the plain run |
| code_a1 | 82 | 290.9 | 98.02 (guessing) |  | 2.31 + 18.29 | 0.1 | SAME AS the plain run |
| prose_n1 | 62 | 280.9 | 83.11 (guessing) |  | 2.30 + 18.20 | 115.5 | SAME AS the plain run |
| prose_a1 | 62 | 291.0 | 83.72 (guessing) |  | 2.30 + 18.04 | 0.0 | SAME AS the plain run |
| analysis_n1 | 113 | 288.4 | 112.27 (guessing) |  | 2.34 + 20.65 | 73.4 | SAME AS the plain run |
| analysis_a1 | 113 | 295.9 | 113.12 (guessing) |  | 2.33 + 20.48 | 0.0 | SAME AS the plain run |
| ops_n1 | 74 | 283.7 | 99.59 (guessing) |  | 2.32 + 19.42 | 100.5 | SAME AS the plain run |
| ops_a1 | 74 | 291.1 | 100.48 (guessing) |  | 2.32 + 19.23 | 0.0 | SAME AS the plain run |
| docs_n1 | 78 | 284.8 | 102.75 (guessing) |  | 2.31 + 19.31 | 84.1 | SAME AS the plain run |
| docs_a1 | 78 | 294.9 | 103.45 (guessing) |  | 2.32 + 19.16 | 0.0 | SAME AS the plain run |
| p3k_n1 | 3,323 | 289.5 | 107.63 (guessing) |  | 2.31 + 20.69 | 35.8 | SAME AS the plain run |
| p3k_a1 | 3,323 | 289.7 | 107.82 (guessing) |  | 2.32 + 20.64 | 0.0 | SAME AS the plain run |
| code_a2 | 82 | 292.7 | 99.79 (guessing) |  | 2.31 + 17.94 | 0.0 | SAME AS the plain run |
| code_n2 | 82 | 284.1 | 99.09 (guessing) |  | 2.30 + 18.08 | 0.0 | SAME AS the plain run |
| prose_a2 | 62 | 289.8 | 83.35 (guessing) |  | 2.31 + 18.13 | 0.0 | SAME AS the plain run |
| prose_n2 | 62 | 281.0 | 82.84 (guessing) |  | 2.31 + 18.25 | 0.0 | SAME AS the plain run |
| analysis_a2 | 113 | 295.1 | 112.79 (guessing) |  | 2.34 + 20.54 | 0.0 | SAME AS the plain run |
| analysis_n2 | 113 | 288.9 | 112.34 (guessing) |  | 2.34 + 20.63 | 0.0 | SAME AS the plain run |
| ops_a2 | 74 | 291.0 | 100.40 (guessing) |  | 2.33 + 19.24 | 0.0 | SAME AS the plain run |
| ops_n2 | 74 | 283.4 | 99.68 (guessing) |  | 2.32 + 19.40 | 0.0 | SAME AS the plain run |
| docs_a2 | 78 | 294.5 | 103.33 (guessing) |  | 2.32 + 19.18 | 0.0 | SAME AS the plain run |
| docs_n2 | 78 | 286.7 | 102.68 (guessing) |  | 2.32 + 19.32 | 0.0 | SAME AS the plain run |
| p3k_a2 | 3,323 | 290.5 | 108.11 (guessing) |  | 2.32 + 20.58 | 0.0 | SAME AS the plain run |
| p3k_n2 | 3,323 | 289.4 | 107.80 (guessing) |  | 2.32 + 20.65 | 0.0 | SAME AS the plain run |
| x69k_n | 68,506 | 266.7 | 64.85 | 15.42 |  | 29.0 | ANSWER256_SAME |
| x19k_a | 18,692 | 279.6 | 69.10 | 14.47 |  | 26.0 | ANSWER256_SAME |
| x34k_a | 33,815 | 274.3 | 68.39 | 14.62 |  | 21.8 | ANSWER256_SAME |
| x69k_a | 68,506 | 267.8 | 67.16 | 14.89 |  | 2.9 | ANSWER256_SAME |
| x95k_a | 95,497 | 263.6 | 65.20 | 15.34 |  | 37.1 | ANSWER256_SAME |
| p1_prof2 | 36 | 196.2 | 65.60 | 15.24 |  | 10.7 | ANSWER64_SAME |
| x19k_prof2 | 18,692 | 242.2 | 60.79 | 16.45 |  | 4.9 | ANSWER64_SAME |
| x69k_prof2 | 68,506 | 233.9 | 59.52 | 16.80 |  | 10.6 | ANSWER64_SAME |
