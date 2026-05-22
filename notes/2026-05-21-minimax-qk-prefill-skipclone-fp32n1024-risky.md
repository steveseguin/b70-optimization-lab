# MiniMax M2.7 Q/K Prefill FP32 Skip-Clone Probe - 2026-05-21

## Goal

Test whether avoiding the custom all-reduce input clone for FP32 Q/K variance tensors up to a 512-token prefill shape can improve prefill/total throughput without changing generated output.

Candidate delta on top of `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`:

```bash
VLLM_XPU_CUSTOM_ALLREDUCE_SKIP_CLONE_FP32_MAX_NUMEL=1024
```

This targets `(tokens, 2)` FP32 Q/K variance reductions through 512 prompt tokens. It does not change the promoted FP16 hidden-state all-reduce clone-safe route.

## Quality Gate

The exact raw145 canary passed:

- Prompt: `prompts/minimax-raw145-tokenhash-canary.txt`
- Output tokens: `64`
- Expected combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Observed combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Passed: `true`
- Degenerate/control/NUL checks: passed

## Throughput Probe

Warm in-process vLLM random-text probe:

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM XPU, TP4, llm-scaler WS INT4 path
- Prompt/output: 512 prompt tokens, 1536 output tokens
- Warmup/measured: 1 warmup, 4 measured repeats
- Mean decode throughput: `94.30268790353395` tok/s
- Mean total throughput: `125.73691720471194` tok/s
- Decode stdev: `1.9665883556648043` tok/s
- Per-repeat decode tok/s: `93.07471067793652`, `93.86994573251376`, `93.06807532943897`, `97.19801987424655`

For comparison, the promoted warm vLLM random-text baseline was about `92.374916` output tok/s and `123.166555` total tok/s on the same p512/n1536 shape.

## Risk

The run emitted PyTorch aliasing warnings for `vllm::all_reduce`:

```text
The output of this custom operator ... must not also be an input ... deprecated and will become an error in PyTorch 2.12.
```

Because the warning points at an aliasing contract violation in the custom op path, this candidate is not promotable even though the exact canary passed and the throughput signal is positive.

## Decision

Do not submit to LocalMaxxing and do not promote this environment. Treat it as a useful signal that FP32 Q/K prefill clone removal may be worth pursuing through an alias-safe in-place custom path.

Next candidate: keep `VLLM_XPU_CUSTOM_ALLREDUCE_SKIP_CLONE_FP32_MAX_NUMEL=0`, raise only the dtype-specific in-place FP32 threshold to `VLLM_XPU_CUSTOM_ALLREDUCE_TINY_FP32_INPLACE_MAX_NUMEL=1024`, then rerun exact-token gates before any throughput comparison.

## Artifacts

- Quality JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-prefill-skipclone-fp32n1024-20260521T030812Z/minimax-qk-prefill-skipclone-fp32n1024-raw145-n64.json`
- Quality log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-prefill-skipclone-fp32n1024-20260521T030812Z/minimax-qk-prefill-skipclone-fp32n1024-raw145-n64.log`
- Warm probe JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-prefill-skipclone-fp32n1024-warm-20260521T031421Z/minimax-qk-prefill-skipclone-fp32n1024-warm-vllm-random-text-p512n1536.json`
- Warm probe log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/qk-prefill-skipclone-fp32n1024-warm-20260521T031421Z/minimax-qk-prefill-skipclone-fp32n1024-warm-vllm-random-text-p512n1536.log`
- Summary data: `data/minimax-m27-qk-prefill-skipclone-fp32n1024-20260521.json`
