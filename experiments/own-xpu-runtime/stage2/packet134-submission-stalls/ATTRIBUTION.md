# Packet134: rank-0 observed gap attribution

CPU reanalysis of packet128b only; no new device measurement or speed claim.

Packet128b: 51.475451 tok/s; overhead gate **failed** (required 52.2).
84 complete sampled cycles: 66 hits, 18 misses. Fixtures 10–16 in every request.

| Interval (ms per sampled cycle) | Hit mean / median | Miss mean / median |
| --- | ---: | ---: |
| Observed compute gap | 1.679212 / 1.327185 | 3.688373 / 3.478446 |
| Snapshot end → speculative begin | 1.593722 / 1.240000 | 1.471186 / 1.116302 |
| Restore end → correction begin | 0.000000 / 0.000000 | 2.046383 / 1.593490 |
| Inside speculative target sequence | 0.084805 / 0.084993 | 0.085040 / 0.084898 |
| Inside correction target sequence | 0.000000 / 0.000000 | 0.085150 / 0.084903 |
| Inside suffix | 0.000685 / 0.000625 | 0.000613 / 0.000625 |
| Host command gaps (overlapping work) | 1.884582 / 2.236825 | 1.910224 / 2.247294 |
| Command gap before speculation | 1.286492 / 1.656665 | 1.305130 / 1.653068 |
| Of that gap: overlap with rank1 draft command | 1.275533 / 1.645044 | 1.293395 / 1.640370 |
| Of that gap: outside rank1 draft command | 0.010959 / 0.011722 | 0.011734 / 0.011657 |
| Command gap before accept | 0.598090 / 0.583099 | 0.001442 / 0.001378 |
| Command gap before rollback | 0.000000 / 0.000000 | 0.602391 / 0.583355 |
| Command gap before correction | 0.000000 / 0.000000 | 0.001260 / 0.001182 |
| Explicit draft-publication wait | 0.007324 / 0.008266 | 0.007827 / 0.008265 |
| Explicit hidden-state wait | 0.001211 / 0.001112 | 0.001261 / 0.001192 |
| Speculative host token preparation | 1.527433 / 1.170172 | 1.406371 / 1.055342 |
| Correction host token preparation | 0.000000 / 0.000000 | 1.941660 / 1.478600 |
| Speculative host enqueue loop | 2.859778 / 2.825290 | 2.896490 / 2.816075 |
| Correction host enqueue loop | 0.000000 / 0.000000 | 2.889826 / 2.883540 |
| Speculative target compute busy union | 11.362531 / 11.359694 | 11.357489 / 11.356621 |
| Correction target compute busy union | 0.000000 / 0.000000 | 11.355503 / 11.355213 |
| Speculative profiling work | 5.210941 / 5.177040 | 5.238781 / 5.175070 |
| Correction profiling work | 0.000000 / 0.000000 | 5.226052 / 5.163360 |

Zero correction cost on hits means the correction did not execute.
The two clocks and overlapping rows must not be added into a wall-time budget.

| Count per sampled half | Hit mean / median | Miss mean / median |
| --- | ---: | ---: |
| Speculative kernels | 564.000000 / 564.000000 | 564.000000 / 564.000000 |
| Correction kernels | 0.000000 / 0.000000 | 564.000000 / 564.000000 |
| Speculative process major faults | 2.454545 / 2.000000 | 1.777778 / 1.500000 |
| Correction process major faults | 0.000000 / 0.000000 | 3.333333 / 3.500000 |

All four original rank0 budget rows reproduce their means and medians within 1e-9 ms.
201 discontinuous compute boundaries are excluded, as in packet128b.
Copies never supply a compute clock. Missing IDs and fixture boundaries are not counted as idle.
The draft-command overlap uses only same-request host steady_clock intervals. It includes host draft
submission/preparation and is not a claim that all of it is draft GPU execution.
The explicit publication wait is largely inside the pre-speculation command gap, not additional cost.

See [README](README.md) for source attribution, limits, decision and reconstruction.
