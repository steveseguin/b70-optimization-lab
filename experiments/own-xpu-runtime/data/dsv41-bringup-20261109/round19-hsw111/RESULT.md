# hsw111: the 16-head groups on the 550 W cards (2026-11-13 19:39-19:56, uncapped)

`OWN_TP_HEADS=4,2,2,4,2,2` (whole groups on cards 0 and 3, the higher power boards) against the default whole-group layout
(16-head groups on cards 2 and 5), tp111. Traces h1 / h4 / h64 identical; every answer and guess log the same.
Plain 111.01 / 111.02 (default) vs 111.42 / 111.05; code 156.93 / 157.61 vs 154.34 / 157.95; analysis 175.45 / 175.18 vs
173.40 / 176.54 tok/s: no difference beyond run-to-run noise. Closed (helper ckm had predicted 0.05-0.09 ms per check).
