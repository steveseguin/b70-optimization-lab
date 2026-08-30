# Qwen3.8-27B Q4_K_M TP2 queue-settle750 c64 pilot

The 750 ms admission pilot formed one exact HTTP cohort but was far too slow for deployment.

- Admission trace: all 64 requests launched within 1 ms, eliminating the earlier 4+60 split.
- Output isolation: 64/64 responses completed with 128 retained token IDs, cached-token counts all zero, and zero cross-base collisions.
- Comparison against the earlier 50 ms c64 shape: 58/64 exact. This is expected to be shape-sensitive and is not the decisive replay gate.
- Diagnostic aggregate rate: **55.22982837146928 tok/s**, with 148.33 s batch wall time. This is explicitly not publishable.
- WDC was disabled and absent from the server log. A manual kernel-journal check found no matching GPU, OOM, or server fault; cleanup was clean.
- The initial pilot qualifier was invoked in the wrong raw-oracle mode and returned nonzero after the valid batch. A normal compact-oracle qualification passed every isolation gate. The runner now uses that normal qualifier for `PILOT_MODE` and still marks pilot speed non-publishable.

The extracted one-cohort oracle is `../data/2026-08-30-qwen38-q4km-tp2-queue-settle750-c64-oracle-digests.json` (SHA-256 `4d4a067856c8372fad601f4874d2aa728db59c4217bb40cd164976d319a19504`). A fresh-server replay was preregistered to determine whether nondeterminism remains below HTTP scheduling.

Evidence: `/mnt/fast-ai/bench-results/qwen38-q4km-tp2-queue-settle750-c64-pilot-20260830-r1-concurrency-control-attempt1/`
