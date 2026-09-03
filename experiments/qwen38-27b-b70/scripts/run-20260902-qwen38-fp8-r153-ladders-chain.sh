#!/usr/bin/env bash
# Ladders-only arms: R153a2 (Triton norm incl. two-row calls), then R153a2 with no
# static compile size (compile_sizes []), both MTP1 and MTP0 c1-c64 ladders.
set -uo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
out=/mnt/fast-ai/bench-results
common=(IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-triton-rmsnorm-r153a2 IMAGE_ID_OVERRIDE=sha256:eac35302baac8e2bca20ac1951e5fcbacd390d86ee84d9df2729a97507f6062c LAYERNORM_SHA256_OVERRIDE=aaa48e514a42b3647b6a487baec69b46fea8a1a9e76a34f0de91dc6f88fe2530 LADDERS_ONLY=1)
env "${common[@]}" ROOT="${out}/qwen38-fp8-triton-rmsnorm-ladders-20260902-r153a2b" "${script_dir}/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh" >"${out}/r153a2-runner.nohup" 2>&1
env "${common[@]}" ROOT="${out}/qwen38-fp8-triton-rmsnorm-ladders-20260902-r154b" \
  COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"compile_sizes":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}' \
  "${script_dir}/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh" >"${out}/r154-runner.nohup" 2>&1
