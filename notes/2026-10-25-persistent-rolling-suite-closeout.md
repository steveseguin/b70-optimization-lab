# Closeout: four-card rolling depth-two full cold suite

Question: can existing-MTP recursive predictions improve four-stage decode while
retaining the two-card engine's output? No draft training was authorized or used.

Result: the complete twelve-prompt suite matched all 5,965 output IDs and final
2,065 target buffers, but full-response median 41.57 tok/s did not improve the
prior four-card 42.31 observation. The two-card service observation remains 47.97,
with a different timing layer. Class-balanced first99 rate 42.68 is separately
reported, without an inferred first99 baseline. All four workers exited zero;
no new GPU fault appeared. No service was restored.

Useful mechanism: persistent cold reset, actual two-step provider consumption,
concurrent target work and rollback now have a full varied-suite audit in
addition to the short complete target/draft qualification. Final long draft
state is authenticated, not independently parity-qualified. Six independent
CPU-reference disagreements remain open. No external score was submitted.

Evidence and recipe:
[complete result](../experiments/own-xpu-runtime/research/continuation-2026-10-25/persistent-rolling-suite-proof/RESULT.md),
[timing](../experiments/own-xpu-runtime/research/continuation-2026-10-25/persistent-rolling-suite-proof/TIMING.md),
[raw-witness review](../experiments/own-xpu-runtime/research/continuation-2026-10-25/persistent-rolling-suite-run-review.json),
[durable archive](../experiments/own-xpu-runtime/research/continuation-2026-10-25/persistent-rolling-suite-durable-archive.json).
All raw journals/state and failed earlier attempts remain preserved. The compact
archive reuses exact prior state payloads and restores all six sealed bundles;
its denser gzip preserves the entire tar byte stream exactly.

Next experiment: change measured layer placement to reduce the first card's
combined target/draft work. Keep the existing binary/arithmetic, bind new cuts
in a distinct plan and repeat correctness gates before a speed interpretation.
Do not repeat the current placement expecting a speed win. Provider relocation
or parent-state ownership changes remain a separate, larger scheduler lever.
