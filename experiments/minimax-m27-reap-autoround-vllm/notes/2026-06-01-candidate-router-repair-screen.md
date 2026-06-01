# 2026-06-01 Candidate Router Repair Screen

Goal: test whether the existing MiniMax candidate-repair router can recover
decode speed on the quality-safe REAP path without changing MoE quality.

## Patch

Archived patch:
`patches/vllm-minimax-candidate-router-fake-20260601.patch`.

The patch registers a fake implementation for
`moe_int4_ops::minimax_m2_candidate_repair_topk`, returning:

- FP32 top-k weights with shape `(num_tokens, top_k)`
- int32 top-k ids with shape `(num_tokens, top_k)`

This only enables TorchDynamo tracing. Runtime math still uses the llm-scaler
XPU repair kernel.

## Quality

Candidate:

- `VLLM_MINIMAX_M2_CANDIDATE_ROUTER_TOPM=16`
- `VLLM_MINIMAX_M2_CANDIDATE_ROUTER_XPU_REPAIR=1`
- `VLLM_MINIMAX_M2_CANDIDATE_ROUTER_MAX_TOKENS=4`
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=0`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=0`
- `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1`

First attempt without the fake registration failed during graph capture:

```text
unsupported operator: moe_int4_ops.minimax_m2_candidate_repair_topk.default
```

After applying the fake registration, async quality passed:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-candidate-router-top16-fake-restore0-20260601T2304.json`
- `384` generated tokens
- `177` distinct generated token IDs
- no NUL/control output
- combined token hash:
  `18eb54bac2c30b1ae5ad6f7ef45066594a03f9968267ebb65e30db14b3e12c1a`

## Benchmark

Warm p512/n1536 direct async benchmark from the same cache root:

- JSON:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T230739Z.json`
- elapsed: `18.422281710983953 s`
- total throughput: `111.16972545148504 tok/s`
- output throughput: about `83.38 tok/s`

## Decision

Reject as a speed path. The compile-enablement patch is useful reference work,
but candidate-router top-16 exact repair does not improve over the current
quality-safe low-83 output tok/s band. The live vLLM source should be restored
to avoid code-hash churn unless this branch is intentionally resumed.

