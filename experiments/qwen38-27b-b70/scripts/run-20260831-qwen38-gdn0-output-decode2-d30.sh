#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-gdn0-output-decode2-20260831-d30
export TARGET_LAYER=0 TARGET_CALL=2 TRACE_HOOK_NAME=qwen38-gdn-output-trace-sitecustomize.py
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-gdn0-output-decode2-d30-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
