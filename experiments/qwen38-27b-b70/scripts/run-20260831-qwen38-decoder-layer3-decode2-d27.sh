#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-decoder-layer3-decode2-20260831-d27
export TARGET_LAYER=3
export TARGET_CALL=2
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-decoder-layer3-decode2-d27-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
