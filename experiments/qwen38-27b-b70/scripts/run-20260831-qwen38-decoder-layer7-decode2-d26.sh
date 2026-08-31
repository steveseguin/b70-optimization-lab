#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-decoder-layer7-decode2-20260831-d26
export TARGET_LAYER=7
export TARGET_CALL=2
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-decoder-layer7-decode2-d26-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
