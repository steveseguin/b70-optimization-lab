#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-decoder-layer1-trace-20260831-d14
export TARGET_LAYER=1
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-decoder-layer1-trace-d14-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
