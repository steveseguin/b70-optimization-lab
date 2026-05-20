# MiniMax M2.7 oneCCL Topo Copy-Engine Screen

Date: 2026-05-20

## Candidate

Current promoted MiniMax M2.7 4x B70 TP4 strict stack plus oneCCL topo copy-engine knobs:

```bash
unset CCL_ALLREDUCE
export CCL_REDUCE_SCATTER_MONOLITHIC_PIPELINE_KERNEL=0
export CCL_ALLGATHERV_MONOLITHIC_PIPELINE_KERNEL=0
```

The rest of the stack matched the promoted quality-valid path:

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
- `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=1`
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1`
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`
- `VLLM_MINIMAX_POST_ATTN_NORM_MOE_CUSTOM_OP=0`
- `VLLM_XPU_ENABLE_XPU_GRAPH=1`
- `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`
- `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`
- `CCL_TOPO_P2P_ACCESS=1`

## Quality

Passed the strict quality gate before benchmarking:

- raw145 n64 exact token hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact token hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat n64/r16: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

## Result

Strict p512/n1536, ctx2048, batch 1, TP4, four repeats:

- Output tok/s: `89.276556`, `89.528251`, `87.099748`, `89.093730`
- Total tok/s: `119.035409`, `119.371001`, `116.132997`, `118.791640`
- Mean output tok/s: `88.749571`
- Mean total tok/s: `118.332762`

Promoted baseline remains `89.314195` output tok/s and `119.085594` total tok/s. This candidate is `0.564624` output tok/s slower on the mean, with a larger slow-tail repeat.

## Conclusion

Rejected. The copy-engine topo knobs are math-preserving and quality-clean, but they reduce repeatability and mean decode throughput on this stack. Keep `CCL_REDUCE_SCATTER_MONOLITHIC_PIPELINE_KERNEL` and `CCL_ALLGATHERV_MONOLITHIC_PIPELINE_KERNEL` unset for promoted graph-enabled MiniMax runs.

No LocalMaxxing submission was made because this is a negative diagnostic result.

Raw summary:

`/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-ccl-topo-copyengines-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T010608Z-summary.json`
