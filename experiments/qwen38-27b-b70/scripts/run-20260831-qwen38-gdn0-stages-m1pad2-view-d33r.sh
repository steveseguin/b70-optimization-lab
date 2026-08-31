#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-gdn0-stages-m1pad2-view-20260831-d33r
export TARGET_LAYER=0
export TARGET_CALL=2
export TRACE_HOOK_NAME=qwen38-gdn-stage-trace-sitecustomize.py
export TRACE_IMAGE=neural-download/vllm-openai-xpu:qwen38-autoround-m1pad2-view-deterministic-r1
export TRACE_IMAGE_ID=sha256:a740562c00ee6ec0b256f411be60aab2d364038d0f8134b2a67100e2d5740c1e
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-int4-m1pad2-view-d33r-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
