# MiniMax M2.7 Delayed MoE + Distributed Residual Probe - 2026-05-21

## Goal

Retest the delayed MoE all-reduce path with distributed residual contribution instead of rank-0-only residual contribution. The goal was to see whether moving the MoE output all-reduce to the next residual boundary could reduce collective overhead while keeping the result mathematically equivalent.

Candidate delta on top of `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`:

```bash
VLLM_MINIMAX_MOE_DELAY_ALLREDUCE=1
VLLM_MINIMAX_M2_DIST_RESIDUAL_ALLREDUCE=1
VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=0
```

## Quality Gate

The exact raw145 canary passed:

- Prompt: `prompts/minimax-raw145-tokenhash-canary.txt`
- Output tokens: `64`
- Expected combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Observed combined token SHA256: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Passed: `true`
- Degenerate/control/NUL checks: passed

This was a useful quality result: the distributed residual formulation did not alter the raw145 exact token output for this gate.

## Throughput Probe

Warm in-process vLLM random-text probe:

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM XPU, TP4, llm-scaler WS INT4 path
- Prompt/output: 512 prompt tokens, 1536 output tokens
- Warmup/measured: 1 warmup, 4 measured repeats
- Mean decode throughput: `91.30841630890737` tok/s
- Mean total throughput: `121.74455507854316` tok/s
- Decode stdev: `0.011691472828797527` tok/s
- Per-repeat decode tok/s: `91.2916672162087`, `91.31760893952253`, `91.31506551428323`, `91.30932356561499`

For comparison, the promoted warm vLLM random-text baseline was about `92.374916` output tok/s and `123.166555` total tok/s on the same p512/n1536 shape.

## Decision

Quality-safe but slower. Do not promote and do not submit to LocalMaxxing.

The result reinforces that the current promoted MoE-output all-reduce-inside-custom-op path is still better than moving that reduction to the next residual boundary, even when the residual contribution is distributed across ranks.

## Artifacts

- Quality JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-delay-distresidual-20260521T033758Z/minimax-moe-delay-distresidual-raw145-n64.json`
- Quality log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-delay-distresidual-20260521T033758Z/minimax-moe-delay-distresidual-raw145-n64.log`
- Warm probe JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-delay-distresidual-warm-20260521T034341Z/minimax-moe-delay-distresidual-warm-vllm-random-text-p512n1536.json`
- Warm probe log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-delay-distresidual-warm-20260521T034341Z/minimax-moe-delay-distresidual-warm-vllm-random-text-p512n1536.log`
- Summary data: `data/minimax-m27-moe-delay-distresidual-negative-20260521.json`
