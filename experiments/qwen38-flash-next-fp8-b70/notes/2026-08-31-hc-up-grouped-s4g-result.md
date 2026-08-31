# Qwen3.8 Flash-Next HC-up grouped S4g result

Date: 2026-08-31

Status: all production M1--64 component cells exact

S4g completed all 640 isolated arms. Grouped E=1 matched contiguous authority
byte-for-byte in all 320 cells: five real checkpoint weights at every integer
M from 1 through 64. Every arm was finite and internally repeatable; rows were
exactly `[M]`; rows, input, and weight stayed unchanged; and all receipt,
stream, process, model, runtime, loader, and evidence hashes passed independent
review.

Grouped was descriptively faster in 320/320 fixed-order cells. Cross-cell
medians were `22.895437` versus `37.956344 us`; the median per-cell reduction
was `41.246%`, with a range of `6.543--64.991%`. These are component timings,
not endpoint attribution or throughput.

Raw summary SHA-256:
`23d7e1bfa8683b8dbaf7d8bac2664477010d84bf1b8e6c6746a5da8027dd4122`.
Combined with the prior all-97 M1 and M64 passes, this closes the production
M1--64 component correctness gate. It authorizes only the separately frozen
source candidate and focused tests, not a build, full-model load, endpoint, or
claim.
