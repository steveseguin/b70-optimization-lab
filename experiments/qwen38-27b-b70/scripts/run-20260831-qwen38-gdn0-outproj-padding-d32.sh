#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-gdn0-outproj-padding-20260831-d32
export TARGET_LAYER=0
export TARGET_CALL=2
export TRACE_HOOK_NAME=qwen38-gdn-outproj-padding-trace-sitecustomize.py
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-gdn0-outproj-padding-d32-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
