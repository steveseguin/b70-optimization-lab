#!/usr/bin/env bash
# R207: all-reduce without the host-side Work.wait() (VLLM_XPU_ALLREDUCE_HOST_WAIT=0) on the R187 configuration.
# a: MTP1 strict pair vs the R187 MTP0 oracle; b: depth-4 strict pair. Waits for pid $1.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
while kill -0 "${1:?pid}" 2>/dev/null; do sleep 30; done
common=(XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 XPU_COMMUNICATOR_SHA256_OVERRIDE=707dcaaa9cb1bd1c5bf15e2bbc4ed44044f85fd5c1578be2d45fe81f1f6f0407 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 VLLM_XPU_ALLREDUCE_HOST_WAIT=0 COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}' IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-allreduce-no-host-wait-r207 IMAGE_ID_OVERRIDE=sha256:8f5b66b8517edceba601b7294a171d75dee4a3ef65f5c42e3548001b148f5c39 STRICT_MTP1_ONLY=1 ORACLE_ROOT=$out/qwen38-fp8-r156-mtp2-no-splitting-full-20260903-r187)
env "${common[@]}" SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":1}' ROOT=$out/qwen38-fp8-r187-allreduce-no-host-wait-mtp1-strict-20260904-r207a bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
env "${common[@]}" SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":4}' ROOT=$out/qwen38-fp8-r187-allreduce-no-host-wait-mtp4-strict-20260904-r207b bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
