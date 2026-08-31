#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-decoder-layer63-decode8-20260831-d21
export TARGET_LAYER=63
export TARGET_CALL=8
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-decoder-layer63-decode8-d21-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
