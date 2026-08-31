#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-gdn0-stages-decode2-20260831-d31r
export TARGET_LAYER=0
export TARGET_CALL=2
export TRACE_HOOK_NAME=qwen38-gdn-stage-trace-sitecustomize.py
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-gdn0-stages-decode2-d31r-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
