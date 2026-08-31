#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-decoder-layer15-trace-20260831-d11
export TARGET_LAYER=15
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-decoder-layer15-trace-d11-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
