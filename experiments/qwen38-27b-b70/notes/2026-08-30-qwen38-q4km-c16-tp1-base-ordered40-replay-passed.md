# Qwen3.8-27B Q4_K_M c16 TP1 ordered-40 deep-base replay: passed

The first fully controlled fresh replay passed **16/16 exact token-ID sequences**.

- Client order: exactly `c000..c015`, 581.49 ms start span inside the 750 ms admission window.
- Server: one monotonic 16-request cohort.
- Outputs: 16/16 complete 128-token sequences, zero cached tokens, complete token-ID isolation, zero collisions.
- Systems: WDC absent, empty kernel-error file, clean shutdown.
- Diagnostic aggregate rate: 12.772774450709221 tok/s.
- Result SHA-256: `862d3c85a49226128c14af8d59747f2eca625e7d1355b4a989739fe7c1c72a80`.

This establishes prompt-to-slot assignment order as the missing determinism control for the earlier comparisons. It does not yet clear the tuned feature stack. The next screen applies the identical ordered client/cohort controls to the tuned TP1 profile, then requires a fresh 16/16 replay against a tuned ordered oracle.

Evidence: `/mnt/fast-ai/bench-results/qwen38-q4km-c16-tp1-base-ordered40-replay-20260830-r1-concurrency-control-attempt1/`
