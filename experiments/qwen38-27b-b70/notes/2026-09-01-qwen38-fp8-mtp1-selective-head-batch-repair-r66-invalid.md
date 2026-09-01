# Qwen3.8 FP8 TP2 MTP1 selective head repair R66: wrong row grouping

R66 intentionally failed closed on the first oracle request. The live sampled
target head had one row at c1, not two:

> `RuntimeError: lm_head batch rows must be divisible by repair rows: 1 vs 2`

No benchmark request completed, so R66 provides no speed or quality result. It
does reveal the correct grouping: this runtime sends one sampled target-head row
per active request even though MTP1 verifies an additional token internally.

The same code supports one-row repair groups. A real-shape forced-repair smoke
made M1 and both rows of M2 bitwise identical. M2 timings were 2.151 ms normal,
2.259 ms on the selective no-repair path, and 6.658 ms when repair was forced
for every row. R67 changes only the group size from two to one.

Structured evidence is in
[`2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r66-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r66-result.json).
