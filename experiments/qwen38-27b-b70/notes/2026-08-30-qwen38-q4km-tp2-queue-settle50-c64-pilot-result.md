# Qwen3.8-27B Q4_K_M TP2 queue-settle c64 pilot

The preregistered control-only oracle pilot passed its admissibility gates. This was not a publishable performance run and no WDC candidate ran.

- Topology: two local B70s, tensor split `1,1`, Q4_K_M, MTP0.
- HTTP shape: 64 simultaneous requests, 128 retained tokens each, context 32768, batch 4096, ubatch 256.
- Scheduler control: explicit 50 ms burst-admission settle window; the server log confirms all 64 slots became active together.
- Output isolation: 64/64 complete token-ID sequences, all cached-token counts zero, zero cross-base collisions.
- Expected batch-shape boundary: c64 matched 38/64 independently generated sequential responses. The pilot exists to freeze the c64 shape, not to claim sequential/c64 equality.
- Diagnostic-only aggregate rate: 147.44371676357042 tok/s. This value must not appear as a promoted result.
- Systems gates: WDC engagement absent, kernel-error file empty, clean server shutdown.

The extracted 64-row c64 token-ID oracle is `../data/2026-08-30-qwen38-q4km-tp2-queue-settle50-c64-oracle-digests.json` (SHA-256 `4be8f8fbd18f2469ab3d0769ad0f1e36bd14ac880236d672f375785d72d3e437`). Two fresh-server exact replays were preregistered before proceeding.

Raw evidence: `/mnt/fast-ai/bench-results/qwen38-q4km-tp2-queue-settle50-c64-pilot-20260830-r1-concurrency-control-attempt1/`
