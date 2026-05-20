# MiniMax next plan after WS source rebuild recovery

Date: 2026-05-20

## Current State

- The source-built WS llm-scaler extension is recovered and quality-clean.
- Latest strict source-rebuild recovery mean: `87.964466` output tok/s / `117.285955` total tok/s.
- Promoted LocalMaxxing result remains: `89.314195` output tok/s / `119.085594` total tok/s.
- Do not promote a new result until it is quality-clean and beats the promoted mean outside normal run noise.

## Plan

1. Add or use a warm-repeat benchmark mode.
   - Goal: avoid reloading 112 GiB of weights and rebuilding process state for every repeat.
   - Success criteria: same quality hashes, same p512/n1536 workload, lower repeat variance, and no change to model math.

2. Profile the slow repeats.
   - Compare `88.82`/`88.89` repeats against the `86.99`/`87.16` repeats.
   - Capture per-token decode timing, graph replay timing, CCL allreduce timing, and GPU utilization around the restored WS path.

3. Resume lower-level source fusion work only from the rebuilt WS state.
   - Highest-value targets remain Q/K variance FP32 allreduce+RMS apply, attention `o_proj` FP16 hidden-state allreduce scheduling, and MoE-output epilogue/allreduce.
   - Avoid Python wrapper-only changes unless timing proves they remove a real hot-path boundary.

4. Keep quality gates strict.
   - Required: raw145 n64/n256 exact hashes, semantic suite, arithmetic repeat, extended sixpack, and at least four throughput repeats before any claim.
   - Any candidate that changes these hashes is rejected even if faster.

5. Submit only meaningful results.
   - LocalMaxxing: submit only new quality-clean wins or broadly useful validated comparisons.
   - GitHub: record all quality-clean negatives, source rebuild lessons, and reproducibility changes.
