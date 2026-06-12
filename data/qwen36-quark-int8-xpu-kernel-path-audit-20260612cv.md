# Qwen3.6 Quark INT8 XPU Kernel Path Audit

Generated: `2026-06-12T20:56:54.851782+00:00`

## Model Shape

- `model_type`: `qwen3_5_moe_text`
- `hidden_size`: `2048`
- `moe_intermediate_size`: `512`
- `num_hidden_layers`: `40`
- `num_experts`: `256`
- `num_experts_per_tok`: `8`
- `num_attention_heads`: `16`
- `num_key_value_heads`: `2`
- `vocab_size`: `248320`

## Main Findings

1. **Current Quark W8A8 INT8 dispatch selects the XPU Int8 MoE backend.**
   - QuarkW8A8Int8MoEMethod calls select_int8_moe_backend.
   - select_int8_moe_backend prioritizes XPU before TRITON on XPU.
   - XPUExpertsInt8 passes is_int8=True into xpu_fused_moe.
   - Impact: Optimization work should target XPU xpu_fused_moe / vllm-xpu-kernels, not Triton.
2. **Runtime wrapper is multi-stage, not a single persistent MoE island.**
   - remap markers: 2
   - W8A8 GEMM calls: 2
   - per-token quant calls: 2
   - gather markers: 1
   - Impact: A fused/persistent c1 topk-8 MoE layerlet could remove several per-token launches and temporary tensors without changing math.
3. **Installed _xpu_C exports base W8A8 grouped GEMM, but not offset/active-offset entry points.**
   - base GEMM exported: True
   - offset GEMM exported: False
   - active-offset GEMM exported: False
   - Impact: The dirty source has route-aware prototypes, but the installed binary is still on the row-count interface. Rebuild/ABI validation is needed before route-aware hotset tests.
4. **Two easy env toggles remain rejected for production.**
   - live VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=None
   - live VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=None
   - Prior notes reject mixed workspace as slower and fused SiLU+quant as quality-failing.
   - Impact: Do not spend another endpoint cycle simply enabling these flags. Use route fixtures and parity gates for new implementations.

## Runtime Endpoint

- Matches: `1`
- PID: `1873149`
- `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE`: `None`
- `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT`: `None`
- `VLLM_XPU_MOE_ONEDNN_SIDECAR_PROBE`: `None`
- `VLLM_XPU_MOE_LIVE_ABI_FILE`: `None`
- `XPU_GRAPH`: `1`
- `VLLM_XPU_ENABLE_XPU_GRAPH`: `1`
- `VLLM_XPU_FORCE_GRAPH_WITH_COMM`: `1`
- `VLLM_XPU_QUARK_W8A8_MOE`: `1`

## Installed Symbol Snapshot

### `_xpu_C`
- Path: `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so`
- Exists: `True`
- Size bytes: `69925576`
- `per_token_quant_int8_xpu`: `True`
- `silu_and_mul_quant_int8_xpu`: `True`
- `cutlass_grouped_gemm_w8a8_int8_interface`: `True`
- `cutlass_grouped_gemm_w8a8_int8_offsets_interface`: `False`
- `cutlass_grouped_gemm_w8a8_int8_active_offsets_interface`: `False`
- `qwen36_moe_onednn_sidecar_probe`: `False`

### `_moe_C`
- Path: `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_moe_C.abi3.so`
- Exists: `True`
- Size bytes: `30928048`
- `per_token_quant_int8_xpu`: `False`
- `silu_and_mul_quant_int8_xpu`: `False`
- `cutlass_grouped_gemm_w8a8_int8_interface`: `False`
- `cutlass_grouped_gemm_w8a8_int8_offsets_interface`: `False`
- `cutlass_grouped_gemm_w8a8_int8_active_offsets_interface`: `False`
- `qwen36_moe_onednn_sidecar_probe`: `False`

## Next Gate

Rebuild or isolate a `vllm-xpu-kernels` candidate that exposes the offset/active-offset W8A8 INT8 entry points, then replay the first-decode route fixture with exact tensor comparison before any endpoint launch.
