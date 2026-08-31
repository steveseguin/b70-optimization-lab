#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-decoder-layer31-prefill-20260831-d16
export TARGET_LAYER=31
export TARGET_CALL=0
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-decoder-layer31-prefill-d16-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
