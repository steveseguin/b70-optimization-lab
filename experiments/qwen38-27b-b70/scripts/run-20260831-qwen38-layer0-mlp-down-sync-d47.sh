#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-layer0-mlp-down-sync-20260831-d47
export TARGET_LAYER=0
export TARGET_CALL=2
export TRACE_HOOK_NAME=qwen38-decoder-layer0-mlp-down-sync-trace-sitecustomize.py
export TRACE_IMAGE=neural-download/vllm-openai-xpu:qwen38-autoround-gdn-int4-prefill-pad512-r1
export TRACE_IMAGE_ID=sha256:03da963d9d9b3b2cfc5cb7d9f1bc0aeb9ebd7e1b9495e3cad4e5b9e5dd4fc493
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-layer0-mlp-down-sync-d47-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
