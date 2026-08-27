# Qwen3.8 27B Q4_K_M + MTP2 — one-B70 candidate package

**Strict headline: `42.636988 tok/s`.** Two fresh servers measured
`42.600910` and `42.673065` on the fixed twelve-prompt/six-class 512-cap
suite. Both attempts passed cache-zero and objective canary gates and matched
all 12 complete token arrays against each other and the same-build target-only
control. The control measured `27.375682 tok/s`, so MTP2 added **55.75%**.

This is a separate deployment from the no-MTP Q4 package because it requires
a second 1.37 GB draft download. Use the complete
[reproduction guide](../../repro/qwen38-27b-q4km-mtp2-tp1-b70/README.md);
it links every required patch and pins the target, draft, server, and SYCL
backend identities.

MTP2 is deliberate. MTP1 was slower (`38.320`), MTP3 was slightly slower
(`42.123`), and MTP5 changed all twelve target outputs and is rejected.

A separate cache-zero exact-depth sweep used unrepeated technical prose,
Python code, and structured documentation at 2K/4K/8K/16K/24K/32K. Each point
is the median of two fresh-server class medians. The exact 32K result is
`36.505065 tok/s` with `39.538 s` TTFT; all **36/36** MTP2 case outputs matched
the fresh matched MTP0 oracle. This is Grade-B real-content context-shape
evidence, not a natural retrieval/task suite. The older repeated-token
diagnostic still diverged at 2K/token 23, so parity is not claimed universally.
See the [structured mixed-content result](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1-result.json).

The directly measured MTP2 HTTP service profile supports 16 slots with 8K
total context (512 nominal tokens per slot). Two fresh servers measured
**68.341 aggregate tok/s at 16 concurrent users**; every throughput response
returned 128 uncached token IDs and **256/256** separate concurrent exact-answer
canaries passed. Multi-user greedy tokens remain batch-shape-dependent, so this
is output-isolation-qualified rather than token-identical at every batch shape.
The 32- and 64-slot profiles failed startup with device OOM and are not
supported on one B70. See the [structured concurrency result](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-http-concurrency-r2-result.json).
