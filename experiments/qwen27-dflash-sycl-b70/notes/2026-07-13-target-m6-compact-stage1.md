# Target M=6 compact verifier: real stage-one parity

Date: 2026-07-13

The guarded target verifier now consumes a separate `I32[6]` result for native
DFlash5 M=6 greedy cycles while preserving host sampler, checkpoint, and
rollback semantics. A same-decode oracle on four previously hash-different
prompts completed 181 compact reads with zero fallbacks and zero acceptance
mismatches against the ordinary full-logit path. Six shorter draft batches
correctly stayed on fallback.

The earlier 12-prompt A/B (`targetm6-jit-A-control-20260713` versus
`targetm6-jit-B-raw-20260713`) is reclassified as a silent no-op: the compact
path never activated. Two guards rejected inert metadata. Chat-template
reasoning tags were populated although no reasoning sampler was active, and
the CLI produced speculative types `[NONE, DRAFT_DFLASH]` by appending DFlash
to the default. Eligibility now matches active sampler behavior and permits
only `NONE`/`DRAFT_DFLASH` with DFlash present.

Evidence:

- oracle result: `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/targetm6-oracle-valid-jit-gpu0-20260713.json`;
- run/logs: `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/targetm6-oracle-valid-jit-gpu0-20260713`;
- counters: mode 1, reads 181, fallbacks 0, compare mismatches 0;
- forced-failure run: `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/targetm6-fallback-jit-gpu0-20260713`; it copied retained full logits, used the ordinary sampler, disabled compact mode, and completed successfully.

This is parity infrastructure, not a speed promotion. Stage one still writes
full `[248320,6]` target logits. The next boundary is the target Q6_K x
quantized-activation Xe2 M=6 output head reduced directly to six IDs.
