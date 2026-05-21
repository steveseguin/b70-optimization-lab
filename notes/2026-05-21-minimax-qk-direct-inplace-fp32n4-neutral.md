# MiniMax M2.7 Q/K Direct In-Place FP32 n4 Neutral Screen - 2026-05-21

## Goal

Test whether the promoted Q/K RMS variance direct in-place all-reduce path should include two-token decode tensors.

The promoted path only used direct in-place FP32 all-reduce for `qk_var.numel() <= 2`, which covers `(1, 2)` Q/K variance tensors. This candidate made that cutoff configurable and tested:

```bash
VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_MAX_NUMEL=4
```

The default remains `2`, so the promoted behavior is unchanged unless the new env var is set.

## Quality

Full strict quality passed on the current 4x B70 promoted stack:

- raw145 n64 exact token hash: passed
- raw145 n256 exact token hash: passed
- semantic suite n64/r2: passed
- arithmetic repeat n64/r16: passed
- extended sixpack n64/r2: passed

This was a useful quality result: the two-token Q/K variance path is safe under the current exact-token and semantic gates. It does not prove a speed win.

## Throughput

Warm text-prompt throughput screen, using explicit PIECEWISE graph config:

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM XPU, TP4, llm-scaler WS INT4 path
- Prompt source: vLLM random text
- Prompt/output: 512 prompt tokens, 1536 output tokens
- Repeats: 4 measured after 1 warmup
- Candidate mean decode: `92.37893496264927` tok/s
- Candidate mean total: `123.17191328353235` tok/s
- Candidate output tok/s range: `92.35860955358888` to `92.41567999618775`
- Candidate output tok/s stdev: `0.025381703821963593`

Paired same-method control with the default cutoff (`2`):

- Control mean decode: `92.33362148462794` tok/s
- Control mean total: `123.11149531283725` tok/s
- Control output tok/s range: `92.29467966250229` to `92.35862614168634`
- Control output tok/s stdev: `0.028955376740153298`

Delta: `+0.04531347802133` output tok/s, or about `+0.04907582%`.

## Full Graph Note

A warm benchmark attempt without explicit PIECEWISE compilation config failed during full decode graph capture:

```text
RuntimeError: The sycl_ext_oneapi_work_group_scratch_memory feature is not yet available for use with the SYCL Graph extension.
```

The stack was in XPU FlashAttention graph capture. This is a runtime/capture incompatibility, not a quality failure. Keep explicit PIECEWISE graph config for current reproducible MiniMax runs unless FlashAttention/SYCL graph support changes.

## Decision

Rejected / not promoted.

The candidate is quality-clean, but the paired control delta is inside normal run noise. It is useful as a default-off diagnostic knob, not as a promoted recipe change. No LocalMaxxing submission was made.

## Artifacts

- Strict summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qk-direct-inplace-fp32n4-20260521-strict-tp4-ctx2048-mbt512-bs256-20260521T072922Z-summary.json`
- Candidate warm JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-direct-inplace-fp32n4-piecewise-warm-20260521T075028Z/minimax-qk-direct-inplace-fp32n4-piecewise-warm-p512n1536.json`
- Paired control warm JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/default-qk-direct-fp32n2-piecewise-warm-20260521T075759Z/minimax-default-qk-direct-fp32n2-piecewise-warm-p512n1536.json`
- Summary data: `data/minimax-m27-qk-direct-inplace-fp32n4-neutral-20260521.json`
- Patch note: `patches/minimax-qk-direct-inplace-max-numel-neutral-20260521.patch`
