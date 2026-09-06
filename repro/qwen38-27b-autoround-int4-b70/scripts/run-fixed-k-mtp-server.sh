#!/usr/bin/env bash
# Qwen3.8-27B AutoRound INT4, fixed-K batch-invariant profile (2026-09-05): launch one vLLM server through the FP8 lane's
# contract-checked launcher with the INT4 identity. Depth via MTP_DEPTH (0 = no speculation; default 4).
#   MODEL_DIR   the gptq-relabelled model directory (built by the relabel builder in this scripts directory); default below
#   IMAGE / EXPECTED_IMAGE_ID  the R256 image (ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:f7696bca...)
#   PORT, VLLM_CACHE_DIR, CONTAINER_NAME, SERVED_MODEL_NAME, TENSOR_PARALLEL_SIZE (2), XPU_DEVICE_MASK (0,1)
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo_root=$(cd -- "${script_dir}/../../.." && pwd)
fp8=${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
depth=${MTP_DEPTH:-4}
spec=""; [[ "${depth}" == 0 ]] || spec="{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":${depth}}"
# XPU_GRAPH=1 (default): capture the decode/verify step as an XPU graph (FULL_DECODE_ONLY, sizes 1-8). On two cards the
# captured verify step drops the per-op all-reduce host waits: depth 4 91.0 tok/s vs 68.2 eager (R247, lossless vs the
# eager MTP0 oracle); on one card it is neutral (+1%). XPU_GRAPH=0 restores the eager R239 configuration.
xpu_graph=${XPU_GRAPH:-1}
if [[ "${xpu_graph}" == 1 ]]; then
  compilation='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8],"max_cudagraph_capture_size":8,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
else
  compilation='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
fi
export IMAGE=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-draft-int4-head-r256}
export EXPECTED_IMAGE_ID=${EXPECTED_IMAGE_ID:-sha256:f7696bcaefab1bc1c93e12cbde630b6e81bed8e00e41154ca2198e246c35dea3}
export EXPECTED_XPU_EXTENSION_SHA256=${EXPECTED_XPU_EXTENSION_SHA256:-271db0d4882124e21ac6a4d080bfeab303fbb08b9ec10e11f21d10fb0723998f}
export EXPECTED_XPU_OPS_SHA256=${EXPECTED_XPU_OPS_SHA256:-c91d6b0d56a68b179a0fb3124ffc2c77082248600b6ad98fa5b5220ae233d4f1}
export EXPECTED_LAYERNORM_SHA256=${EXPECTED_LAYERNORM_SHA256:-50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8}
export MODEL_DIR=${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel}
export MODEL_MANIFEST=${MODEL_MANIFEST:-${script_dir}/../manifests/model-gptq-relabel-r212.json}
# DRAFT_HEAD_INT4=1 (default): the MTP draft passes use a draft-only INT4 copy of the lm_head (R257: depth 4 112.4 tok/s vs
# 91.0 with the FP16 head; acceptance 3.51 vs 3.00); the target verifier head stays FP16, so outputs are unchanged.
export QUANTIZATION=gptq VLLM_XPU_FP8_BLOCK_W8A16=0 VLLM_XPU_DRAFT_LM_HEAD_INT4=${DRAFT_HEAD_INT4:-1} VLLM_XPU_W4A16_DETERMINISM_PAD=0
export VLLM_BATCH_INVARIANT=1 VLLM_XPU_GDN_SPLIT_MIXED=1 VLLM_XPU_GDN_SPEC_GROUP=${VLLM_XPU_GDN_SPEC_GROUP:-16}
export VLLM_XPU_GEMMA_RMSNORM_TRITON=0 VLLM_XPU_RMSNORM_TRITON=0 VLLM_XPU_ENABLE_XPU_GRAPH=${xpu_graph}
export COMPILATION_CONFIG=${COMPILATION_CONFIG:-${compilation}}
export SPECULATIVE_CONFIG=${SPECULATIVE_CONFIG:-${spec}}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-int4-fixed-k-mtp${depth}} SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen38-int4-fixed-k-mtp${depth}}
export PORT=${PORT:-18134} MAX_NUM_BATCHED_TOKENS=${MAX_NUM_BATCHED_TOKENS:-1024} GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.95}
export CONTAINER_MEMORY=${CONTAINER_MEMORY:-12g} CONTAINER_MEMORY_SWAP=${CONTAINER_MEMORY_SWAP:-16g}
if [[ "${depth}" == 0 ]]; then
  unset SPECULATIVE_CONFIG
  exec "${fp8}/run-w8a16-mtp0-strict-server.sh"
fi
exec "${fp8}/run-w8a16-mtp1-server.sh"
