# tl105: check budget by tokens on tp105 (2026-11-12 20:24)

tp105 with `OWN_FL=3 OWN_U3_NOPAIR=1` + draft vocabulary, code prompt, timeline of checks 20-119 (single queue:
per-kernel times are valid). `dsv41_ck_by_m.py tl_ck.txt tl_ck-spec.txt 19 <card>` (first index 19, not 20: with
20 the M labels are shifted by one). Timeline (69 MB) kept out of git: dsv41-work/runs/tl105/.

Device busy per check, ms (card 2; card 0 within 0.1 except dense -0.5 and exchanges +0.6):

| part | M=1 | M=2 | M=3 | M=4 | M=5 | M=6 | per extra token (M2->5) |
|---|---|---|---|---|---|---|---|
| dense rows | 3.26 | 4.65 | 5.21 | 4.79 | 5.61 | 5.77 | 0.32 |
| experts + router | 2.53 | 3.76 | 4.76 | 5.77 | 6.52 | 7.62 | 0.92 |
| exchanges | 1.71 | 2.30 | 2.62 | 3.30 | 3.73 | 4.15 | 0.48 |
| attention | 0.52 | 0.61 | 0.66 | 0.67 | 0.72 | 0.48 | 0.04 |
| norms + mix | 0.80 | 0.51 | 0.53 | 0.73 | 0.87 | 0.75 | 0.12 |
| total | 8.82 | 11.83 | 13.79 | 15.25 | 17.45 | 18.77 | 1.87 |

Checks per M: 32 / 30 / 20 / 6 / 8 / 4. Read: the slope is now 1.87 ms per extra token (was ~2.5 at tp90), half of it
experts (mostly new experts' bytes and decode; that this is at the bandwidth floor is NOT measured, see round19-costk notes). The step from 1 to 2 tokens costs +3.0 ms, of which dense
rows +1.4 (one-token GEMV forms -> weight-stationary forms + PaceK) against ~0.3 per later token: the "ck2" helper
works on 2-3-token forms of the one-token GEMVs (`dsv41-work/ck2/`), target ~-1 ms at M = 2-3 (~-0.75 ms per cycle,
~+5 % guessing).
