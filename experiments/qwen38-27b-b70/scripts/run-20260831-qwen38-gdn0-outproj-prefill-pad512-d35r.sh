#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-gdn0-outproj-prefill-pad512-20260831-d35r
export TARGET_LAYER=0
export TARGET_CALL=2
export TRACE_HOOK_NAME=qwen38-gdn-outproj-prefill-pad512-stage-trace-sitecustomize.py
export TRACE_IMAGE=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
export TRACE_IMAGE_ID=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-gdn-outproj-prefill-pad512-d35r-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
