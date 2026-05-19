# MiniMax M2.7 Site-Labeled Allreduce Timing

Date: 2026-05-19

## Summary

Ran diagnostic-only rank-0 synchronized timing probes on the current promoted MiniMax stack after adding temporary allreduce labels around MiniMax/MoE collective sites. Both probes passed the raw145 n64 exact token hash, so the timing instrumentation did not change the sampled output for the canary.

These are not throughput results. `VLLM_XPU_DECODE_TIMING_SYNC=1` adds explicit synchronization and makes generation much slower. The purpose is to identify where the visible collective waits are, not to report tok/s.

## Artifacts

- First log: `/home/steve/bench-results/minimax-m2.7-strict-candidates/site-labeled-timing/site-labeled-currenthigh-rank0-sync-n64-20260519T224106Z.log`
- First JSON: `/home/steve/bench-results/minimax-m2.7-strict-candidates/site-labeled-timing/site-labeled-currenthigh-rank0-sync-n64-20260519T224106Z.json`
- RowParallel follow-up log: `/home/steve/bench-results/minimax-m2.7-strict-candidates/site-labeled-timing/site-labeled-rowparallel-currenthigh-rank0-sync-n64-20260519T224823Z.log`
- RowParallel follow-up JSON: `/home/steve/bench-results/minimax-m2.7-strict-candidates/site-labeled-timing/site-labeled-rowparallel-currenthigh-rank0-sync-n64-20260519T224823Z.json`
- Data: `data/minimax-m27-site-labeled-allreduce-timing-20260519.json`

## Quality

Both diagnostic probes matched the promoted raw145 n64 combined token hash:

- Expected and observed: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`

## Timing Signal

The first probe successfully labeled the MoE-output allreduce inside the MiniMax MoE custom-op boundary. The second probe attempted to label `RowParallelLinear` reductions by prefix, but those labels did not survive the compiled graph path; the remaining unlabeled FP16 hidden-state collective shapes and counts still match the attention `o_proj` pattern.

Largest buckets from the row-parallel follow-up:

- Q/K variance-shaped FP32 allreduce, `(1, 2)`: `1186.268281 ms` total, `186` calls, `6.377786 ms` average
- Unlabeled FP16 hidden-state allreduce, likely attention `o_proj`, `(1, 3072)`: `618.361679 ms` total, `189` calls, `3.271755 ms` average
- Labeled MoE output allreduce, `(2, 3072)`: `591.250477 ms` total, `124` calls, `4.768149 ms` average
- Labeled MoE output allreduce, `(1, 3072)`: `504.048505 ms` total, `186` calls, `2.709938 ms` average
- Unlabeled FP16 hidden-state allreduce, likely attention `o_proj`, `(2, 3072)`: `472.817282 ms` total, `126` calls, `3.752518 ms` average
- Prefill/profile FP16 hidden allreduce, `(512, 3072)`: `436.521821 ms` total, `63` calls, dominated by a large warmup/profile max
- Q/K variance-shaped FP32 allreduce, `(2, 2)`: `334.059389 ms` total, `124` calls, `2.694027 ms` average
- Local lm-head argmax: `46.335786 ms` total, `66` calls, `0.702057 ms` average

## Interpretation

The earlier attention `o_proj` Python custom-op wrapper was rejected because it preserved quality but slowed the current high. This diagnostic explains why: simply changing Python boundaries does not reduce the actual XPU/CCL dependency latency. The visible synchronized cost is still spread across repeated small Q/K variance collectives plus the two per-layer hidden-state collective families: attention `o_proj` and MoE output.

The next useful implementation work should target lower-level math-preserving fusion or scheduling around these collectives:

- Q/K variance allreduce plus scale/apply remains a high-frequency FP32 `(1, 2)` path, but previous max-token and apply-scale variants showed quality or speed risks. Any next Q/K work should be a narrow helper/mutating path with exact canaries.
- Attention `o_proj` needs a lower-level row-parallel GEMM-plus-allreduce or graph/collective scheduling improvement, not another Python custom-op wrapper.
- MoE output allreduce is now proven visible even when moved inside the MiniMax MoE custom-op boundary. The next MoE candidate should look at fusing the output allreduce with the MoE epilogue or reducing graph dependency latency around that custom op.

The temporary source and installed-venv diagnostic patches were reverted after the probes and `py_compile` passed.
