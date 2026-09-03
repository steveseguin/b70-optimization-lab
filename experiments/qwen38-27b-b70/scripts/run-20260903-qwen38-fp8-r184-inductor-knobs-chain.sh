#!/usr/bin/env bash
# R184 chain (2026-09-03): published R156, depth 2, async on, one Inductor knob per arm via COMPILATION_CONFIG.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
common=(XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 QUERY_ONLY=1 QUERY_KINDS=mtp1 QUERY_LAUNCH="256 64 512" QUERY_SCRIPT=$S/repro-qwen38-fp8-mtp2-phantom-first-token.py SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":2}' IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-split-mixed-r156 IMAGE_ID_OVERRIDE=sha256:173660ec18c6e98a14b9a4f573922abe9d3414999056f07ab5c3c14b55d6ceb0)
pre='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false'
env "${common[@]}" COMPILATION_CONFIG="${pre},\"allow_buffer_reuse\":false}}" ROOT=$out/qwen38-fp8-r156-mtp2-phantom-inductor-buffer-reuse-off-20260903-r184b bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
env "${common[@]}" COMPILATION_CONFIG="${pre},\"max_fusion_size\":1}}" ROOT=$out/qwen38-fp8-r156-mtp2-phantom-inductor-fusion-off-20260903-r184c bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
env "${common[@]}" COMPILATION_CONFIG="${pre},\"pattern_matcher\":false}}" ROOT=$out/qwen38-fp8-r156-mtp2-phantom-inductor-pattern-matcher-off-20260903-r184d bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
