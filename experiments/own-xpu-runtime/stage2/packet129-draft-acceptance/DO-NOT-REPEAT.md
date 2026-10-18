# Packet129 boundaries

- Never use suite acceptance to select the format, prefix or corpus.
- Never publish candidate guesses, overwrite the target or count diagnostic
  timings as a speed result. Production remains the only proposer in this job.
- Suffix shadowing is valid for this expert-only change. It does not qualify
  future changes before attention/cache append.
- Current expert activation, gate/up and down choices are production. A fused
  expert activation requires a corresponding candidate implementation.
- Preserve publisher FP8 values and scales. BF16 rounding of their product is
  another candidate, not exact FP32 decoding.
- Do not allocate a second full expert bank: rank1's arena cannot hold it.
- Preserve oracle and source symlinks; real CLI checks must use the actual tree.
- CPU resource limits never belong in runtime imports or device-launch paths.
- No candidate-as-production timing proposal until independent acceptance passes.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md). The experiment itself
remains pending its coordinator-owned device diagnostic.
