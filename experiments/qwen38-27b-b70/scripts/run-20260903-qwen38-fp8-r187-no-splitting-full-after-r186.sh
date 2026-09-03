#!/usr/bin/env bash
# R187 (2026-09-03): published R156 + COMPILATION_CONFIG splitting_ops=[] (whole-graph Inductor compile), depth-2 MTP,
# full R147-style campaign: same-config MTP0 oracle pair (G1), depth-2 strict pairs (G2/G3), probe (G5), ladders (G6).
# Waits for the R186 chain (pid $1).
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
while kill -0 "${1:?r186 chain pid}" 2>/dev/null; do sleep 30; done
env XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8   GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":2}'   COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'   IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-split-mixed-r156 IMAGE_ID_OVERRIDE=sha256:173660ec18c6e98a14b9a4f573922abe9d3414999056f07ab5c3c14b55d6ceb0   ROOT=$out/qwen38-fp8-r156-mtp2-no-splitting-full-20260903-r187 bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
