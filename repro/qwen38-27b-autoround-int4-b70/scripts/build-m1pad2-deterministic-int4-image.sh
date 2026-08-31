#!/usr/bin/env bash
set -euo pipefail

export PATCH_RELATIVE=experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-onednn-int4-m1pad2-view-determinism-20260831.patch
export EXPECTED_PATCH_SHA256=f2218adbacd8ae331b4c1a25eeca4f4e6529dcdfdb6629949220da1fbb973f88
: "${IMAGE:=neural-download/vllm-openai-xpu:qwen38-autoround-m1pad2-view-deterministic-r1}"
export IMAGE

exec bash "$(dirname "$0")/build-current-deterministic-int4-image.sh"
