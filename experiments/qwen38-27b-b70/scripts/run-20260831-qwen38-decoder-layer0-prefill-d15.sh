#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-decoder-layer0-prefill-20260831-d15
export TARGET_LAYER=0
export TARGET_CALL=0
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-decoder-layer0-prefill-d15-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
