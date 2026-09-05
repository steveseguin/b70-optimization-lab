#!/usr/bin/env bash
# Qwen3.8-27B AutoRound INT4, fixed-K batch-invariant profile (2026-09-05): launch one vLLM server through the FP8 lane's
# contract-checked launcher with the INT4 identity. Depth via MTP_DEPTH (0 = no speculation; default 4).
#   MODEL_DIR   the gptq-relabelled model directory (scripts/make-gptq-relabel.py); default below
#   IMAGE / EXPECTED_IMAGE_ID  the R228 image (ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:aaf920b0...)
#   PORT, VLLM_CACHE_DIR, CONTAINER_NAME, SERVED_MODEL_NAME, TENSOR_PARALLEL_SIZE (2), XPU_DEVICE_MASK (0,1)
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo_root=$(cd -- "${script_dir}/../../.." && pwd)
fp8=${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
depth=${MTP_DEPTH:-4}
spec=""; [[ "${depth}" == 0 ]] || spec="{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":${depth}}"
compilation='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
export IMAGE=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-gdn-spec-group-r228}
export EXPECTED_IMAGE_ID=${EXPECTED_IMAGE_ID:-sha256:aaf920b04224cb3f4be881ae41dbef4fa7841f4ab26fbbe09e4e780fe361ff7d}
export EXPECTED_XPU_EXTENSION_SHA256=${EXPECTED_XPU_EXTENSION_SHA256:-271db0d4882124e21ac6a4d080bfeab303fbb08b9ec10e11f21d10fb0723998f}
export EXPECTED_XPU_OPS_SHA256=${EXPECTED_XPU_OPS_SHA256:-c91d6b0d56a68b179a0fb3124ffc2c77082248600b6ad98fa5b5220ae233d4f1}
export EXPECTED_LAYERNORM_SHA256=${EXPECTED_LAYERNORM_SHA256:-50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8}
export MODEL_DIR=${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel}
export MODEL_MANIFEST=${MODEL_MANIFEST:-${script_dir}/../manifests/model-gptq-relabel-r212.json}
export QUANTIZATION=gptq VLLM_XPU_FP8_BLOCK_W8A16=0 VLLM_XPU_DRAFT_LM_HEAD_INT4=0 VLLM_XPU_W4A16_DETERMINISM_PAD=0
export VLLM_BATCH_INVARIANT=1 VLLM_XPU_GDN_SPLIT_MIXED=1 VLLM_XPU_GDN_SPEC_GROUP=${VLLM_XPU_GDN_SPEC_GROUP:-16}
export VLLM_XPU_GEMMA_RMSNORM_TRITON=0 VLLM_XPU_RMSNORM_TRITON=0 VLLM_XPU_ENABLE_XPU_GRAPH=0
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
