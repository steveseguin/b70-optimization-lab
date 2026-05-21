# MiniMax M2.7 Q/K FP32 In-Place n1024 Probe - 2026-05-21

## Goal

Retest the positive Q/K prefill clone-removal signal with an alias-safe custom-op route.

Candidate delta on top of `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`:

```bash
VLLM_XPU_CUSTOM_ALLREDUCE_SKIP_CLONE_FP32_MAX_NUMEL=0
VLLM_XPU_CUSTOM_ALLREDUCE_TINY_FP32_INPLACE_MAX_NUMEL=1024
```

The intent was to cover FP32 Q/K variance all-reduce shapes through `(512, 2)` without returning a tensor that aliases an input from the out-of-place custom op.

## Quality Gate

The exact raw145 canary passed:

- Prompt: `prompts/minimax-raw145-tokenhash-canary.txt`
- Output tokens: `64`
- Expected combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Observed combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Passed: `true`
- Degenerate/control/NUL checks: passed

The quality log did not contain the `vllm::all_reduce` PyTorch aliasing warning seen in the prior skip-clone probe.

## Throughput Probe

Warm in-process vLLM random-text probe:

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM XPU, TP4, llm-scaler WS INT4 path
- Prompt/output: 512 prompt tokens, 1536 output tokens
- Warmup/measured: 1 warmup, 4 measured repeats
- Mean decode throughput: `92.75441156733979` tok/s
- Mean total throughput: `123.67254875645304` tok/s
- Decode stdev: `0.03153326426241411` tok/s
- Per-repeat decode tok/s: `92.73973684105654`, `92.7382299416305`, `92.80169716345996`, `92.73798232321215`

For comparison, the promoted warm vLLM random-text baseline was about `92.374916` output tok/s and `123.166555` total tok/s on the same p512/n1536 shape.

## Decision

Quality-safe but neutral. The improvement is too small to treat as a new promoted result, especially because the prior risky skip-clone probe showed higher but noisy throughput. Do not submit this result to LocalMaxxing.

This does support one conclusion: expanding the alias-safe FP32 Q/K in-place threshold does not appear to degrade output quality on the raw145 exact-token canary, but it also does not unlock a meaningful decode win by itself.

## Artifacts

- Quality JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-prefill-tinyfp32-inplace-n1024-20260521T032237Z/minimax-qk-prefill-tinyfp32-inplace-n1024-raw145-n64.json`
- Quality log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-prefill-tinyfp32-inplace-n1024-20260521T032237Z/minimax-qk-prefill-tinyfp32-inplace-n1024-raw145-n64.log`
- Warm probe JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-prefill-tinyfp32-inplace-n1024-warm-20260521T032828Z/minimax-qk-prefill-tinyfp32-inplace-n1024-warm-vllm-random-text-p512n1536.json`
- Warm probe log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-prefill-tinyfp32-inplace-n1024-warm-20260521T032828Z/minimax-qk-prefill-tinyfp32-inplace-n1024-warm-vllm-random-text-p512n1536.log`
- Summary data: `data/minimax-m27-qk-prefill-tinyfp32-inplace-n1024-neutral-20260521.json`
