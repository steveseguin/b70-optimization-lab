#!/usr/bin/env bash
# R163: graph-on ladders on R156; R164: MTP depth-2 strict pair on R156.
set -uo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
out=/mnt/fast-ai/bench-results
common=(IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-split-mixed-r156 IMAGE_ID_OVERRIDE=sha256:173660ec18c6e98a14b9a4f573922abe9d3414999056f07ab5c3c14b55d6ceb0 XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1)
env "${common[@]}" ROOT="${out}/qwen38-fp8-r156-graph-on-ladders-20260903-r163" LADDERS_ONLY=1 XPU_GRAPH=1 \
  COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2,"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}' \
  "${script_dir}/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh" >"${out}/r163-runner.nohup" 2>&1
env "${common[@]}" ROOT="${out}/qwen38-fp8-r156-mtp2-strict-20260903-r164" STRICT_MTP1_ONLY=1 RESUME_FROM= ORACLE_ROOT="${out}/qwen38-fp8-gdn-split-mixed-full-20260903-r156f" \
  SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":2}' \
  "${script_dir}/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh" >"${out}/r164-runner.nohup" 2>&1
