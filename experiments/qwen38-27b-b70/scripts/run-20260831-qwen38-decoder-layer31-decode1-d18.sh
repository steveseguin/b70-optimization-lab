#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-decoder-layer31-decode1-20260831-d18
export TARGET_LAYER=31
export TARGET_CALL=1
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-decoder-layer31-decode1-d18-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
