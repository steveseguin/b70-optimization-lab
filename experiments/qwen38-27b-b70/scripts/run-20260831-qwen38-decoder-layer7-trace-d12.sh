#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-decoder-layer7-trace-20260831-d12
export TARGET_LAYER=7
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-decoder-layer7-trace-d12-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
