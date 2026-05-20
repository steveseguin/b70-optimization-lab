# MiniMax MoE Full-Forward Max2 Current-High Retest

Date: 2026-05-20 UTC

## Summary

Retested `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=2` on the
current promoted MiniMax M2.7 4x B70 stack. This is the same quality-promoted
recipe as the `89.314195` output tok/s result, except the MiniMax MoE
full-forward custom-op guard is narrowed from max 4 tokens to max 2 tokens.

The candidate is quality-clean but not faster. It should not be promoted or
submitted to LocalMaxxing.

## Candidate

Key env delta:

```bash
VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1
VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=2
```

Promoted-stack settings retained:

- `VLLM_XPU_USE_LLM_SCALER_MOE=1`
- `VLLM_XPU_USE_LLM_SCALER_MOE_WS=1`
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`
- `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=0`
- `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1`
- `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1`
- `VLLM_XPU_CUSTOM_ALLREDUCE_TINY_FP32_INPLACE_MAX_NUMEL=2`
- `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=0`
- `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1`
- `VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS=4`
- `VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE=1`
- `VLLM_MINIMAX_QK_RMS_APPLY_TP_SCALE=0`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS=2`
- `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=1`
- `VLLM_MINIMAX_POST_ATTN_NORM_MOE_CUSTOM_OP=0`
- `VLLM_XPU_ENABLE_XPU_GRAPH=1`
- `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`
- `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`
- `CCL_TOPO_P2P_ACCESS=1`

`CCL_ALLREDUCE`, `CCL_REDUCE_SCATTER_MONOLITHIC_PIPELINE_KERNEL`,
`CCL_ALLGATHERV_MONOLITHIC_PIPELINE_KERNEL`, and
`CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK` were left unset.

## Quality

Passed the full strict quality gate before benchmarking:

- raw145 n64 exact token hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact token hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat n64/r16: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

The arithmetic-repeat and extended-sixpack teardown logs printed
`Bad address (src/pipe.cpp:367)` plus Python resource-tracker warnings. The
strict summary stayed `quality_passed`, all hashes matched, and benchmark
repeats completed. Treat this as known runtime teardown noise, not as a speed
promotion signal.

## Result

Shape: p512/n1536, ctx2048, batch 1, TP4, MBT512, block256.

Four repeats:

- Output tok/s: `89.232342`, `89.187419`, `89.067492`, `89.481110`
- Total tok/s: `118.976456`, `118.916559`, `118.756656`, `119.308147`
- Mean output tok/s: `89.242091`
- Mean total tok/s: `118.989455`

Promoted baseline:

- Output tok/s: `89.314195`
- Total tok/s: `119.085594`
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`

Delta: `-0.072104` output tok/s, about `-0.081%`.

## Decision

Rejected. Do not submit to LocalMaxxing. Keep
`VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4` for the current
promoted recipe.

The useful lesson is that max2 is close to max4 under the current-high cache
and runtime, but still below it on a four-repeat mean. The earlier lower max2
screen was not the deciding data point; this current-high retest confirms max4
remains the better strict setting.

## Artifacts

- Strict summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-fullforward-max2-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T020134Z-summary.json`
- Quality directory: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-fullforward-max2-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T020134Z-quality`
- Local data: `data/minimax-m27-moe-full-forward-max2-currenthigh-negative-20260520.json`
