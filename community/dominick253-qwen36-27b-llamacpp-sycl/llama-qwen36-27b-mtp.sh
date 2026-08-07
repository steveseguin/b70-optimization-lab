#!/usr/bin/env bash
# Qwen3.6-27B MTP Q4_K_M on one Intel Arc Pro B70 via llama.cpp SYCL.
# Run one independent instance per GPU; set GPU_INDEX=0/1 and PORT=8001/8002.
set -euo pipefail

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-$((8001 + GPU_INDEX))}"
LLAMA_ROOT="${LLAMA_ROOT:-/path/to/llama.cpp}"
MODEL="${MODEL:-/path/to/models/Qwen3.6-27B-MTP-GGUF/Qwen3.6-27B-Q4_K_M.gguf}"
ONEAPI_ROOT="${ONEAPI_ROOT:-/opt/intel/oneapi}"

# setvars may return non-zero after exporting a usable environment.
set +u
source "${ONEAPI_ROOT}/setvars.sh" >/dev/null 2>&1 || true
set -u

export ONEAPI_DEVICE_SELECTOR="level_zero:${GPU_INDEX}"
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_USE_LEVEL_ZERO_API=1
export GGML_SYCL_ENABLE_FLASH_ATTN=1
export GGML_SYCL_FA_ONEDNN=1
export GGML_SYCL_ENABLE_GRAPH=0

exec "${LLAMA_ROOT}/build-sycl/bin/llama-server" \
  --model "${MODEL}" \
  --host "${HOST:-127.0.0.1}" \
  --port "${PORT}" \
  --ctx-size 175000 \
  --n-gpu-layers 99 \
  --device SYCL0 \
  --split-mode none \
  --main-gpu 0 \
  --parallel 1 \
  --batch-size 2048 \
  --ubatch-size 2048 \
  --cache-type-k f16 \
  --cache-type-v f16 \
  --cache-type-k-draft f16 \
  --cache-type-v-draft f16 \
  --flash-attn on \
  --spec-type draft-mtp \
  --spec-draft-n-max 2 \
  --spec-draft-p-min 0.0 \
  --temp 0.6 \
  --top-p 0.95 \
  --top-k 20 \
  --min-p 0.0 \
  --presence-penalty 0.0 \
  --repeat-penalty 1.0 \
  --fit off
