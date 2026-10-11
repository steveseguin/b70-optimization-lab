# Packet 20 launch micro-benchmark, attempt a (2026-10-11 14:36–14:43 UTC, PCI 0000:27:00.0)

Five of the issuing methods completed (150 rows, every output verified) before the
program stopped on its own error: it asked for profiling information from an event of
a queue created without `enable_profiling` (the next method in the list). It then
parked instead of exiting ("ownership retained"). The process was idle (fdinfo: no
engine cycles, no active memory); the coordinator ended it by PID at 14:43:21 UTC and
the kernel log stayed clean. No GPU fault.

Median wall time per launch, repeats after the first, microseconds:

| Method | elementwise, 17 pointers (100 / 1,000 / 4,000) | GEMV-like (100 / 1,000 / 4,000) |
| --- | ---: | ---: |
| explicit dependencies, in-order queue | 4.72 / 4.97 / 4.36 | 4.37 / 4.34 / 4.37 |
| explicit dependencies, out-of-order queue | 5.67 / 4.58 / 4.88 | 4.50 / 4.45 / 4.46 |
| explicit, host wait after every kernel | 9.49 / 9.51 / 9.56 | 9.51 / 9.53 / 9.58 |
| in-order queue, implicit ordering | 6.35 / 4.21 / 4.08 | 5.73 / 4.20 / 4.08 |
| in-order queue, events discarded | 5.04 / 3.52 / 3.39 | 4.99 / 3.51 / 3.40 |

**Reading.** Issuing a small kernel through SYCL on this card costs 3.4–5 µs, and about
9.5 µs even with a host wait after each one. That is six to ten times less than the
30 µs per launch assumed from the integrated runs. The integrated runtime's cost per
launch therefore comes from its own submission path or from the kernels themselves,
not from the act of issuing. Command-graph replay, raw Level Zero lists and the
fusion-by-eight baseline did not run in this attempt.
