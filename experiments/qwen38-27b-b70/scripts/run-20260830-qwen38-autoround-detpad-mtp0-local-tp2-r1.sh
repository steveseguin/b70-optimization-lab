#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)

exec env \
  CAMPAIGN=qwen38-autoround-detpad-mtp0-local-tp2-20260830-r1 \
  PREREG="${repo}/experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-autoround-detpad-mtp0-local-tp2-r1-prereg.md" \
  IMAGE=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1 \
  EXPECTED_IMAGE_ID=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136 \
  EXPECTED_XPU_EXTENSION_SHA256=c5e9c9a505f64e0e4be819191ef091c09bfb2af153c6c7c341c80e8ebed2e620 \
  EXPECTED_GDN_LIBRARY_SHA256=2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355 \
  MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround \
  GPU_IDS=0,1 \
  MIN_HOST_MEMORY_GIB=8 \
  CONTAINER_MEMORY=12g \
  CONTAINER_MEMORY_SWAP=36g \
  "${script_dir}/run-qwen38-autoround-deterministic-mtp0-campaign.sh"
