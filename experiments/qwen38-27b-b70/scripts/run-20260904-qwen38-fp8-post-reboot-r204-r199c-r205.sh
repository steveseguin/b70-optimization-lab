#!/usr/bin/env bash
# Post-reboot chain (2026-09-04 morning): R204 depth-5 probe + two ladders, R199c short profiler capture, R205 depth-6 pair repeat.
# Run from a clean boot (the r152 preflight checks it). Waits for pid $1 if given.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
bash $S/run-20260904-qwen38-fp8-r204-mtp5-ladders-after-r203.sh 999999
bash $S/run-20260904-qwen38-fp8-r199c-decode-profile-short-after-r204.sh 999999
env XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1   COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}' IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-split-mixed-r156 IMAGE_ID_OVERRIDE=sha256:173660ec18c6e98a14b9a4f573922abe9d3414999056f07ab5c3c14b55d6ceb0   SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":6}' STRICT_MTP1_ONLY=1 ORACLE_ROOT=$out/qwen38-fp8-r156-mtp2-no-splitting-full-20260903-r187 ROOT=$out/qwen38-fp8-r187-mtp6-strict-repeat-20260904-r205 bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
