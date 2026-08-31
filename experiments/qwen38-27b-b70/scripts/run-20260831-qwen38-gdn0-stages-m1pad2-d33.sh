#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-gdn0-stages-m1pad2-20260831-d33
export TARGET_LAYER=0
export TARGET_CALL=2
export TRACE_HOOK_NAME=qwen38-gdn-stage-trace-sitecustomize.py
export TRACE_IMAGE=neural-download/vllm-openai-xpu:qwen38-autoround-m1pad2-deterministic-r1
export TRACE_IMAGE_ID=sha256:ac3084c3f75bb48491cdcf3cf88ba35b602b9db70eac8f189834d2b6a13d6f86
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-int4-m1pad2-repair-d33-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
