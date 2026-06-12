# Qwen3.6 Accepted Lane Manifest

- Created: `1781301369`
- Endpoint health: `True`
- Quality smoke pass: `True`
- Quality baseline match: `True`
- Old token provenance pass: `False`
- Corrected p512/o512 decode: `99.188 tok/s`
- vLLM decode: `10.063 ms/token`
- Cache files: `4221` files, `1184728587` bytes
- Cache digest: `754a30c22b94952565827ce6e0431c6589da23c3e540cebb3e15909313bef54e`
- Launcher diagnostic scrub complete: `True`
- Gate status: `accepted_quality_baseline_with_stale_token_sentinel`

## Gate Notes

- No-thinking quality smoke and baseline comparison passed.
- Old exact-token provenance did not pass on this clean cache; treat token sentinels as cache-versioned.
- Accepted launcher scrubs rejected diagnostic MoE env vars.
- p512/o512/c1 speed artifact is present and parseable.

## Next Candidate Requirements

- Beat this manifest's corrected p512/o512/c1 decode speed on the same current model.
- Pass the no-thinking quality suite and baseline comparison.
- Report strict old-token provenance separately from cache-versioned clean-cache token baselines.
- Record cache root digest, AOT path hashes, extension SHA256, and launcher env scrub state.
- For kernel-path changes, pass graph-path or live compiled-path tensor parity before endpoint promotion.

## Extension Symbols

- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so` sha `d2c6cc8d1cc92c3671a3a9357bed6c5783bdbcf505ee663d16f2e42f1e46ce8c` symbols `{'cutlass_grouped_gemm_w8a8_int8_interface': True, 'cutlass_grouped_gemm_w8a8_int8_offsets_interface': False, 'cutlass_grouped_gemm_w8a8_int8_active_offset_interface': False, 'qwen36_moe_onednn_sidecar': False}`
- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/libgrouped_gemm_xe_2.so` sha `d2d2ecdf96f8d56549baa708cc46658827f601fb55141d6ab793fb1a24a5009e` symbols `{'cutlass_grouped_gemm_w8a8_int8_interface': False, 'cutlass_grouped_gemm_w8a8_int8_offsets_interface': False, 'cutlass_grouped_gemm_w8a8_int8_active_offset_interface': False, 'qwen36_moe_onednn_sidecar': False}`
- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so` sha `c0db2d8c90295c1f26bac00a4851a90e65ff36f40b42d1632e4532f3c388bb3f` symbols `{'cutlass_grouped_gemm_w8a8_int8_interface': False, 'cutlass_grouped_gemm_w8a8_int8_offsets_interface': False, 'cutlass_grouped_gemm_w8a8_int8_active_offset_interface': False, 'qwen36_moe_onednn_sidecar': False}`
