# Qwen3.8 FP8 TP2 MTP1 target-head invariance R65: exact but too slow

R65 passed the strict c1/c2 identity gate: both c2 batches were 2/2 exact
against fresh sequential oracles, all cache counters stayed at zero, and the
harness exited successfully under `--require-output-identity`.

It failed the preregistered performance floor. Median c2 aggregate throughput
was **36.003 tok/s**, versus a **68.373 tok/s** floor. Median c1 was only
20.158 tok/s. The deterministic persistent matmul makes the full 124,160-column
FP16 verifier head substantially slower, so this implementation is not a
shipping candidate and changes no public result.

The positive diagnostic is localization: changing only `ParallelLMHead`
arithmetic removed the c2 divergence. R66 therefore keeps the normal fast head,
checks the top-two margin cheaply, and recomputes only a near-tie request group
at the c1 two-row shape. A real-shape microbenchmark measured 2.159 ms for the
normal M4 head, 2.271 ms for the selective no-repair path, and 6.673 ms when
repair was deliberately forced for all groups.

Structured evidence is in
[`2026-09-01-qwen38-fp8-mtp1-target-head-batch-invariant-r65-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-target-head-batch-invariant-r65-result.json).
