# Current Promoted Results

Date: 2026-06-10

## Qwen3.6 35B-A3B Quark W8A8 INT8

Current Qwen production-candidate speed result:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: local vLLM XPU TP4 plus local `vllm-xpu-kernels`
- Recipe: Quark W8A8 INT8 weights, BF16 activation/runtime dtype, 32K context, native XPU dense INT8 linear, native XPU INT8 MoE backend, XPU PIECEWISE graph capture, and clone-safe custom-op all-reduce collectives.
- Single request: `94.52` output tok/s after first chunk, `93.21` output tok/s end-to-end, mean TTFT `76.10 ms` for p512/n512 streaming completions.
- Restart refresh: after the device-lost recovery and baseline relaunch, p512/n512 streaming measured `94.31` output tok/s after first chunk, `94.13` corrected after-first, `93.00` end-to-end, and `76.46 ms` mean client TTFT across four repeats. This is within noise of the promoted single-request baseline, so the restart did not materially change the accepted recipe. Artifact: `data/qwen36-quark-int8-graph32k-single-refresh-20260610.json`.
- Aggregate reference: `1604.00` output tok/s wall at 48 concurrent p512/n256 streaming completions. Earlier short-prompt chat probe reached `~2080` aggregate tok/s at 48.
- Quality: text exact canaries, JSON field semantics, 16-repeat hash stability, and 8K-class long-context needle recall passed.
- Restore smoke after the rejected fused-kernel experiment also passed exact canaries, JSON field semantics, repeat stability, and long-context recall.
- Primary artifacts: `notes/2026-06-09-qwen36-quark-int8-xpu-graph-custom-collectives.md`, `data/qwen36-quark-int8-graph32k-customar-20260609.json`, `data/qwen36-quark-int8-graph32k-quality-20260609.json`, `data/qwen36-quark-int8-graph32k-restore-smoke-20260609.json`, `data/qwen36-quark-int8-graph32k-concurrency-20260609.json`, `data/qwen36-quark-int8-graph32k-single-metrics-20260609.json`.
- Repro patches: `patches/vllm-qwen36-quark-w8a8-int8-xpu-graph-20260609.patch`, `patches/vllm-xpu-kernels-qwen36-quark-w8a8-int8-xpu-20260609.patch`.
- Rejected candidate: `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1` sped up an isolated activation/quant microbench but failed the quality gate by returning `58` instead of `60` for the arithmetic canary. Artifact: `data/qwen36-quark-int8-graph32k-fused-siluq-quality-20260609.json`. Keep this env unset.
- MoE kernel microbench: accepted Qwen3.6-shaped INT8 MoE rows 1/2/4/8 measured `298.96/304.89/272.78/283.87 us` with exact staged-path match. The rejected fused SiLU+quant diagnostic measured `238.91/232.35/229.18/260.70 us` for the same rows but drifted from the accepted staged output and remains disabled. Artifacts: `data/qwen36-quark-int8-moe-kernels-20260609.json`, `data/qwen36-quark-int8-moe-kernels-fused-siluq-20260609.json`.
- MoE scratch diagnostic: preallocated BF16/INT32 scratch in the staged path stayed exact versus `xpu_fused_moe` and measured rows 1/2/4/8 at `210.15/206.06/206.46/240.51 us`; rows 16/32 measured `322.35/489.85 us`. This is a diagnostic, not yet a runtime promotion, because production needs a mixed-dtype workspace route for BF16 activations, INT32 routing maps, INT8 activations, and FP32 scales. Artifact: `data/qwen36-quark-int8-moe-kernels-prealloc-20260610.json`.
- Mixed-workspace runtime screen: `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1` reused BF16/INT32 MoE scratch through vLLM's workspace manager and passed the smoke quality suite, but single-request p512/n512 speed measured `93.62` corrected after-first output tok/s and `92.52` end-to-end output tok/s, below the promoted `94.52` / `93.21`. Decision: reject for now; do not enable in production. Artifacts: `data/qwen36-quark-int8-mixedws-smoke-20260610.json`, `data/qwen36-quark-int8-mixedws-single-metrics-20260610.json`.
- RMSNorm plus INT8 per-token-quant fusion screen: the direct XPU fused kernel microbench was `37-46%` faster for hidden size 2048, but the fused kernel requires BF16 weight while the live Qwen norm path uses a FP32 transformed weight, producing small quant drift in direct checks. The endpoint compiled with `VLLM_XPU_FUSE_RMS_INT8_QUANT=1`, but the actual graph still had zero `rms_norm_dynamic_per_token_quant` calls, so the pattern did not match and was not benchmarked for promotion. Decision: reject/no-op for now; baseline restored. Patch artifacts: `patches/vllm-qwen36-quark-int8-runtime-candidates-20260610.patch`, `patches/vllm-xpu-kernels-qwen36-quark-int8-runtime-candidates-20260610.patch`.
- RMSNorm plus INT8 BF16-input/FP32-weight fused-kernel follow-up: a kernel patch was added to preserve Qwen's FP32 transformed norm weight and BF16 rounding before INT8 scale/quantization, but the build/test loop failed before quality or speed validation. The full oneAPI 2026 build was killed by the OS while compiling unrelated `paged_decode_xe2.cpp`; the partial `_C` binary then hung inside `torch.ops._C.rms_norm_dynamic_per_token_quant` on a `1x2048` tensor, and the rebuilt `_xpu_C` broke `per_token_quant_int8_xpu` with `RuntimeError: Invalid argument` plus Level Zero abort. Decision: reject; do not wire this patch into graph replacement. Artifacts: `notes/2026-06-10-qwen36-rms-int8-bf16fp32-rejected.md`, `data/qwen36-quark-int8-rms-int8-bf16fp32-rejected-20260610.json`, `patches/vllm-xpu-kernels-qwen36-rms-int8-bf16-fp32-rejected-20260610.patch`.
- Build-loop improvement: direct CMake `_C`-only build was validated with oneAPI 2025.3, B70-only AOT, and all non-basic extensions disabled. It built and installed a temp `_C.abi3.so` without touching the package or compiling attention/MoE/_xpu_C targets; import smoke passed and `torch.ops._C.rms_norm_dynamic_per_token_quant` was registered. Use this for future exact fused-kernel iteration before graph replacement. Artifacts: `notes/2026-06-10-vllm-xpu-kernels-c-only-build.md`, `data/qwen36-vllm-xpu-kernels-c-only-build-20260610.json`, `scripts/build-vllm-xpu-kernels-c-only.sh`.
- Reliability incident: after the rejected local fused-kernel diagnostics, the accepted backend later hit `UR_RESULT_ERROR_DEVICE_LOST` during an external chat completion request and exited `139`. No stale workers remained, all four B70s still enumerated, and the accepted TP4 32K baseline was relaunched successfully; backend and frontdoor `/v1/models` were ready again. Future unsafe extension diagnostics should stop or isolate the serving backend first. Artifacts: `notes/2026-06-10-qwen36-device-lost-restart.md`, `data/qwen36-quark-int8-device-lost-restart-20260610.json`.
- Graph inspection after custom-op collectives: c10d/allreduce analyzers now return zero because the promoted backend routes collectives through `torch.ops.vllm.all_reduce`. The compiled graph still shows roughly 220 dense `per_token_quant_int8_xpu` assignments, 220 `int8_gemm_w8a8` assignments, 101 `vllm_ir.rms_norm.default` assignments, 81 custom all-reduce assignments, and 40 MoE custom-op assignments. This points the next work at dense RMS/quant/GEMM boundaries and exact MoE epilogues, not at the old c10d call path. Artifacts: `data/qwen36-quark-int8-mixedws-aot-allreduce-boundaries-20260610.json`, `data/qwen36-quark-int8-mixedws-aot-collectives-20260610.json`.

Next Qwen targets: fix RMS/quant graph-pattern matching only if the exact FP32-weight semantics can be preserved, investigate dense W8A8 small-M GEMM epilogues and allocation reuse, revisit MoE scratch reuse only if it improves full-model speed, fuse MoE activation plus second-stage quant only if it reproduces current rounding/scaling behavior, and keep aggregate throughput tracked with the 1/2/4/8/16/32/48 concurrency harness.

## MiniMax M2.7

Section last updated: 2026-05-19

Current strict quality-passed speed result:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM `0.20.1-local`, XPU TP4
- Recipe: FP16 activations, AutoRound INT4 W4A16, default XPU FlashAttention v2, XPU PIECEWISE graph, exact MiniMax router-logits path feeding llm-scaler INT4 MoE work-sharing decode with `VLLM_XPU_USE_LLM_SCALER_MOE_WS=1`, `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`, `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=0`, clone-safe compiled allreduce custom-op via `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1` plus `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1`, direct in-place Q/K variance allreduce+scale via `VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE=1`, final MoE output allreduce moved inside the MoE custom-op boundary via `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=1`, and decode-sized router-linear plus fused MoE wrapped in a guarded MiniMax full-forward custom-op boundary via `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1` with `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`
- Shape: p512/n1536, ctx2048, batch 1
- Result: `89.314195` output tok/s, `119.085594` total tok/s, mean of four clean long repeats
- Output tok/s repeats: `[88.927239, 89.396677, 89.527321, 89.405544]`
- Quality: raw145 exact n64/n256 hashes, semantic suite, 16-repeat arithmetic, and extended sixpack all passed before benchmarking
- Delta: `+0.43%` output tok/s over the previous strict high (`88.927945`) and `+10.81%` over the earlier MoE-WS FlashAttention/PIECEWISE baseline (`80.602755`)
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`

Primary artifacts:

- Current strict clean high: `notes/2026-05-19-minimax-moe-full-forward-customop-plus-output-ar.md`, `data/minimax-m27-moe-full-forward-customop-plus-output-ar-20260519.json`, `data/localmaxxing-minimax-m27-autoround-moe-full-forward-customop-plus-output-ar-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-moe-full-forward-customop-plus-output-ar-p512n1536-20260519.response.json`, `patches/minimax-moe-full-forward-customop-plus-output-ar-20260519.md`
- Previous MoE output-allreduce custom-op high: `notes/2026-05-19-minimax-moe-output-allreduce-inside-customop.md`, `data/minimax-m27-moe-output-allreduce-inside-customop-20260519.json`, `data/localmaxxing-minimax-m27-autoround-moe-output-allreduce-inside-customop-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-moe-output-allreduce-inside-customop-p512n1536-20260519.response.json`, `patches/minimax-moe-output-allreduce-inside-customop-20260519.patch`
- Current clean direct Q/K variance follow-up: `notes/2026-05-19-minimax-qk-direct-inplace-scale.md`, `data/minimax-m27-qk-direct-inplace-scale-20260519.json`, `data/localmaxxing-minimax-m27-autoround-qk-direct-inplace-scale-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-qk-direct-inplace-scale-p512n1536-20260519.response.json`, `patches/minimax-qk-direct-inplace-scale-20260519.patch`
- Cleaner Q/K-helper follow-up: `notes/2026-05-19-minimax-qk-helper-tinyfp32-inplace.md`, `data/minimax-m27-qk-helper-tinyfp32-inplace-20260519.json`, `data/localmaxxing-minimax-m27-autoround-qk-helper-tinyfp32-inplace-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-qk-helper-tinyfp32-inplace-20260519.response.json`
- Cleaner alias-correct tiny-FP32 in-place path: `notes/2026-05-19-minimax-qkvar-inplace-fp32n2.md`, `data/minimax-m27-qkvar-inplace-fp32n2-20260519.json`, `data/localmaxxing-minimax-m27-autoround-qkvar-inplace-fp32n2-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-qkvar-inplace-fp32n2-20260519.response.json`, `patches/minimax-qkvar-inplace-fp32n2-20260519.patch`
- Previous warning-prone speed headline: `notes/2026-05-18-minimax-qkvar-skipclone-fp32n2-win.md`, `data/minimax-m27-qkvar-skipclone-fp32n2-win-20260518.json`, `data/localmaxxing-minimax-m27-autoround-qkvar-skipclone-fp32n2-p512n1536-20260518.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-qkvar-skipclone-fp32n2-p512n1536-20260518.response.json`, `patches/minimax-qkvar-skipclone-fp32n2-20260518.patch`
- Recent Q/K helper guard rejections: `notes/2026-05-19-minimax-qk-helper-max1-currenthigh-quality-fail.md`, `data/minimax-m27-qk-helper-max1-currenthigh-quality-fail-20260519.json`, `notes/2026-05-19-minimax-qk-helper-max2-currenthigh-negative.md`, `data/minimax-m27-qk-helper-max2-currenthigh-negative-20260519.json`
- QKV narrow-split negative: `notes/2026-05-19-minimax-qkv-narrow-split-negative.md`, `data/minimax-m27-qkv-narrow-split-negative-20260519.json`, `patches/minimax-qkv-narrow-split-negative-20260519.patch`
- Current-high CCL fabric-vertex override rejection: `notes/2026-05-19-minimax-currenthigh-ccl-fabric-vertex-off-negative.md`, `data/minimax-m27-currenthigh-ccl-fabric-vertex-off-negative-20260519.json`
- Current-high skip-contiguous rejection: `notes/2026-05-19-minimax-currenthigh-skip-redundant-contiguous-negative.md`, `data/minimax-m27-currenthigh-skip-redundant-contiguous-negative-20260519.json`

Previous promoted MiniMax baselines:

- MiniMax MoE full-forward custom-op high: `89.314195` output tok/s, `119.085594` total tok/s, LocalMaxxing `cmpct6t4m007fnw01yjdtlcs4`.
- MoE output-allreduce-inside-custom-op: `88.927945` output tok/s, `118.570593` total tok/s, LocalMaxxing `cmpco63q90052nw01ov1zxvwp`.
- Direct Q/K variance in-place scale: `88.501953` output tok/s, `118.002604` total tok/s, LocalMaxxing `cmpc8cmqm0060pc016g5l5ukh`.
- Q/K helper plus alias-correct tiny-FP32 in-place op: `88.313105` output tok/s, `117.750807` total tok/s, LocalMaxxing `cmpc5xmm6005jpc01k84dxd14`.
- Alias-correct tiny-FP32 in-place op: `88.103866` output tok/s, `117.471821` total tok/s, LocalMaxxing `cmpc1dxgv0052pc01s1j9i37l`.
- Warning-prone tiny-FP32 skip-clone headline: `88.748424` output tok/s, `118.331232` total tok/s, LocalMaxxing `cmpbz7lyc004rpc019jburzqv`.
- Clone-safe custom allreduce without tiny-FP32 clone elision: `87.279129` output tok/s, `116.372172` total tok/s, LocalMaxxing `cmpbsqm4l001qpc0199azisgz`.
- No-attention-delay logits-WS baseline without clone-safe compiled allreduce custom-op: `82.404268` output tok/s, `109.872357` total tok/s, LocalMaxxing `cmpbifcx3013bmn01747cxix8`.
- Delayed-attention logits-WS baseline: `81.758267` output tok/s, `109.011023` total tok/s, LocalMaxxing `cmpay7th600bbmn01v6csyaro`.
- Earlier MoE-WS FlashAttention/PIECEWISE baseline: `80.602755` output tok/s, `107.470340` total tok/s, LocalMaxxing `cmpasdq5v007nmn019elaut3s`.

Recent quality-safe rejections and screens:

- Q/K helper max1 current-high: lowered `VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS` from `4` to `1`. It failed `raw145-n64-exact` before benchmarking: expected `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`, observed `21404821eb70a2ee3de9e82c039b5cbb5c9eef884c5019579f442c6a272a9c5a`. Output was deterministic and non-degenerate, but exact-token drift violates the quality rule. Decision: reject, do not benchmark, do not submit to LocalMaxxing.
- Q/K helper max2 current-high: lowered `VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS` from `4` to `2`. It passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `88.541226` output tok/s / `118.054968` total tok/s. Decision: reject and do not submit to LocalMaxxing because it is `0.772970` output tok/s below the promoted mean. Keep Q/K helper max tokens at `4`.
- Current-high CCL fabric-vertex override: `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0` passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `89.037858` output tok/s / `118.717144` total tok/s across four repeats, `0.276337` output tok/s below the promoted mean. The arithmetic-repeat shutdown log also printed oneCCL/PMI `Broken pipe` and `ccl::v1::exception` teardown errors. Decision: reject, do not submit to LocalMaxxing, and keep this env unset.
- Current-high skip-redundant-contiguous: `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1` passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `89.141961` output tok/s / `118.855948` total tok/s across four repeats, `0.172235` output tok/s below the promoted mean. The extended-sixpack and first benchmark-repeat logs printed `Bad address (src/pipe.cpp:367)` during shutdown. Decision: reject and do not submit to LocalMaxxing.
- QKV narrow-split: `VLLM_MINIMAX_QKV_NARROW_SPLIT=1` replaced `qkv.split(...)` view extraction with explicit `Tensor.narrow()` views around the Q/K RMS helper. It passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `88.802625` output tok/s / `118.403500` total tok/s. Decision: reject and do not submit to LocalMaxxing because it is `0.511570` output tok/s below the promoted mean. The lesson is that split-view selection is not a meaningful decode bottleneck under the current XPU graph replay path.
- MiniMax MoE full-forward guard sweep: max1 `89.031893`, max2 `88.854010`, max3 `88.886159`, max4 `89.314195`, max512 `85.209082` output tok/s. Decision: keep `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`.
- Post-attention norm plus MoE custom-op: quality passed but measured `89.007143` output tok/s / `118.676191` total tok/s. Reject.
- Full-forward plus callable-cache: quality passed but measured `88.828891` output tok/s / `118.438521` total tok/s. Reject.
- MoE output-allreduce plus callable-cache stack: quality passed but measured `88.912296` output tok/s / `118.549728` total tok/s. Reject.
- MiniMax MoE WS skip-redundant-contiguous without full-forward custom-op: quality passed but measured `88.885135` output tok/s / `118.513514` total tok/s. Reject.
- Current-high `--block-size 128` failed `raw145-n64-exact`; keep `--block-size 256`.
- `VLLM_MINIMAX_MOE_FINAL_INPLACE_ALLREDUCE=1` failed the first strict quality gate before benchmarking; do not use larger FP16 hidden-state in-place allreduce under the current graph recipe.
- `VLLM_XPU_LOGITS_CHUNKED_GATHER=32768` failed 16-repeat arithmetic determinism; do not use chunked logits gather until deterministic.
- Exact-shape XCCL microbench found raw decode-sized allreduces around `15-17 us`; full-model loss is dominated by framework/compiler/graph boundaries around collectives, not raw CCL latency alone.
- `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=4096` and `=2048` both passed quality but were slower than dtype-specific tiny-FP32 routing. Keep generic in-place threshold unset or `0`.

Detailed historical candidate screens remain in `notes/` and `data/`. The local lab copy of `CURRENT.md` may include a longer running chronology than this concise repo status file.

## Qwen3.6 27B

The quality-preserving Qwen targets remain separate from MiniMax AutoRound:

- Q4_0 GGUF TP3 remains the current Qwen decode-speed focus.
- Static FP8 TP4 remains the preferred long-context Qwen layout.
- AutoRound/INT4 results should not be compared as equal-quality replacements for FP8/BF16/GGUF without separate quality validation.

## Next Optimization Targets

- Use the MiniMax MoE full-forward custom-op result as the current strict baseline for future code work.
- Keep `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`; the guard-size sweep found max4 as the local optimum.
- Keep `VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS=4`; max1 failed exact quality and max2 was quality-safe but slower.
- Keep `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=0`; generic thresholds are quality-safe but slower than dtype-specific tiny-FP32 routing.
- Keep `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK` unset; the current-high retest was slower and showed oneCCL shutdown noise.
- Continue targeting true XPU fused-boundary work: hidden allreduce plus residual/RMSNorm, Q/K variance allreduce plus Q/K RMS apply, MoE output plus epilogue, and final lm-head/projection boundaries.
- Preserve vLLM's proven allreduce semantics unless a candidate has an exact repeatability proof across fresh graph/cache captures.
- Keep strict quality gates as promotion blockers; do not promote logits/router/argmax shortcuts unless they pass raw exact hashes, semantic checks, arithmetic repeat, and extended sixpack.
- Keep speculative decode optional and quality-gated; no current promoted MiniMax result uses speculation.
