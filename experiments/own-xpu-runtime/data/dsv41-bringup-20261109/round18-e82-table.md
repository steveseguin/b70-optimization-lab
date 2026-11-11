| run | prompt tokens | reading tok/s | answer tok/s | ms per step (plain) | draft + check ms | disk MiB in answers | checks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| h16 |  |  | 64.91 | 15.41 |  | 4.5 | TRACE_IDENTICAL, IDS40_SAME |
| h5 |  |  | 66.02 | 15.15 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| h1 |  |  | 63.60 | 15.72 |  | 0.8 | TRACE_IDENTICAL, IDS40_SAME |
| h16i |  |  | 66.10 | 15.13 |  | 0.0 | TRACE_IDENTICAL, IDS40_SAME |
| p1 |  |  | 74.55 | 13.41 |  | 12.2 | SPEED128_SAME |
| x19k_plain | 18,692 | 279.5 | 67.79 | 14.75 |  | 31.3 |  |
| x19k_idx | 18,692 | 280.2 | 68.21 | 14.66 |  | 0.0 | ANSWER256_SAME_AS_x19k_plain |
| x19k_spec | 18,692 | 278.0 | 89.76 (guessing) |  | 2.31 + 20.78 | 7.9 | SAME AS the plain run |
| x34k_plain | 33,815 | 271.7 | 65.30 | 15.31 |  | 25.2 |  |
| x34k_idx | 33,815 | 273.8 | 66.24 | 15.10 |  | 0.0 | ANSWER256_SAME_AS_x34k_plain |
| x34k_spec | 33,815 | 270.3 | 91.59 (guessing) |  | 2.31 + 21.90 | 6.5 | SAME AS the plain run |
| x69k_plain | 68,506 | 257.5 | 60.42 | 16.55 |  | 23.6 |  |
| x69k_idx | 68,506 | 261.7 | 59.43 | 16.83 |  | 25.4 | ANSWER256_SAME_AS_x69k_plain |
| x69k_spec | 68,506 | 256.2 | 81.32 (guessing) |  | 2.30 + 22.78 | 38.9 | SAME AS the plain run |
| x95k_plain | 95,497 | 246.8 | 56.60 | 17.67 |  | 35.3 |  |
| x95k_idx | 95,497 | 252.7 | 56.64 | 17.66 |  | 35.1 | ANSWER256_SAME_AS_x95k_plain |
| x19k_one | 18,692 | 70.2 | 68.69 | 14.56 |  | 0.7 | ANSWER16_SAME_AS_x19k_plain |
| x69k_prof2 | 68,506 | 228.7 | 53.22 | 18.79 |  | 4.6 | ANSWER32_SAME_AS_x69k_plain |
