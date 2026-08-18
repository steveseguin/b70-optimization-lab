#!/usr/bin/env bash
# Qwen3.8-27B Cold Fusion GAIN V1.1 MTP — llama.cpp SYCL launcher (single B70)
# Contributor: dominick253 — community-reported, 2026-08-18
#
# Placeholders to replace before running:
#   $MODEL_PATH    - path to the Cold Fusion GAIN V1.1 MTP Q4_K_M GGUF
#   $PORT          - HTTP port (default 8001)
#   $GPU_INDEX     - Level Zero device index (default 0)
#   $LLAMA_SERVER  - path to llama-server binary (b10472 SYCL build)
set -euo pipefail

MODEL_PATH="${MODEL_PATH:?set MODEL_PATH to the Q4_K_M MTP GGUF}"
PORT="${PORT:-8001}"
GPU_INDEX="${GPU_INDEX:-0}"
LLAMA_SERVER="${LLAMA_SERVER:-llama-server}"

# oneAPI environment
source /opt/intel/oneapi/setvars.sh --silent 2>/dev/null || true

# SYCL / Level Zero configuration
export ONEAPI_DEVICE_SELECTOR="level_zero:${GPU_INDEX}"
export GGML_SYCL_USE_LEVEL_ZERO_API="1"
export GGML_SYCL_ENABLE_FLASH_ATTN="1"
export GGML_SYCL_ENABLE_GRAPH="0"

# Community Level Zero graph shim (required for this configuration)
# Source: https://github.com/opencode-ai fixes collection — replace with your path
if [[ -n "${L0GRAPHSHIM:-}" && -f "${L0GRAPHSHIM}" ]]; then
  export LD_PRELOAD="${L0GRAPHSHIM}"
fi

exec "${LLAMA_SERVER}" \
  --model "${MODEL_PATH}" \
  --alias "Qwen38-27b-gpu${GPU_INDEX}" \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --ctx-size 160000 \
  --parallel 1 \
  --n-gpu-layers 99 \
  --device SYCL0 \
  --split-mode none \
  --main-gpu 0 \
  --batch-size 4096 \
  --ubatch-size 2048 \
  --threads 16 \
  --cache-type-k f16 \
  --cache-type-v f16 \
  --cache-type-k-draft f16 \
  --cache-type-v-draft f16 \
  --flash-attn on \
  --spec-type draft-mtp \
  --spec-draft-n-max 2 \
  --spec-draft-p-min 0.1 \
  --temp 1.0 \
  --top-p 0.95 \
  --top-k 20 \
  --min-p 0.0 \
  --presence-penalty 0.0 \
  --repeat-penalty 1.0 \
  --jinja \
  --reasoning auto \
  --fit off
