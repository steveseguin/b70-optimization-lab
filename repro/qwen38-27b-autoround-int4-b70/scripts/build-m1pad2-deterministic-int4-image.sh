#!/usr/bin/env bash
set -euo pipefail

export PATCH_RELATIVE=experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-onednn-int4-m1pad2-determinism-20260831.patch
export EXPECTED_PATCH_SHA256=1ffbdc4b0e1220011dfa77d859c2c625d5d4896117c0fe221a5f163bc2ba044e
: "${IMAGE:=neural-download/vllm-openai-xpu:qwen38-autoround-m1pad2-deterministic-r1}"
export IMAGE

exec bash "$(dirname "$0")/build-current-deterministic-int4-image.sh"
