# MiniMax MoE Full-Forward Index Custom-Op Negative

Date: 2026-05-20 UTC

## Summary

Tested an index-based variant of the promoted MiniMax MoE full-forward custom-op
path. The intent was to remove a small Python/framework boundary inside the
current winning MoE wrapper by avoiding byte-string `LayerName` resolution and
dict lookup on every decode-layer call.

The candidate is quality-clean but slower. It should not be promoted or
submitted to LocalMaxxing.

## Candidate

New env delta:

```bash
VLLM_MINIMAX_MOE_FULL_FORWARD_INDEX_CUSTOM_OP=1
```

Promoted-stack settings retained:

- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1`
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`
- `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=1`
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

## Result

Shape: p512/n1536, ctx2048, batch 1, TP4, MBT512, block256.

Four repeats:

- Output tok/s: `88.729770`, `88.827083`, `88.431778`, `88.604402`
- Total tok/s: `118.306361`, `118.436110`, `117.909037`, `118.139203`
- Mean output tok/s: `88.648258`
- Mean total tok/s: `118.197678`

Promoted baseline:

- Output tok/s: `89.314195`
- Total tok/s: `119.085594`
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`

Delta: `-0.665937` output tok/s, about `-0.75%`.

## Decision

Rejected. Do not submit to LocalMaxxing. Keep the promoted string/LayerName
full-forward custom-op path and leave
`VLLM_MINIMAX_MOE_FULL_FORWARD_INDEX_CUSTOM_OP` unset.

The useful lesson is that the extra Python dictionary/LayerName resolution was
not the limiting boundary. The index variant is math-preserving, but the custom
op signature and graph path did not improve scheduling or dispatch enough to
matter, and the measured four-repeat mean was lower.

## Artifacts

- Strict summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-fullforward-index-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T023839Z-summary.json`
- Quality directory: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-fullforward-index-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T023839Z-quality`
- Local data: `data/minimax-m27-moe-full-forward-index-negative-20260520.json`
- Patch note: `patches/minimax-moe-full-forward-index-customop-negative-20260520.md`
- Patch: `patches/minimax-moe-full-forward-index-customop-negative-20260520.patch`
