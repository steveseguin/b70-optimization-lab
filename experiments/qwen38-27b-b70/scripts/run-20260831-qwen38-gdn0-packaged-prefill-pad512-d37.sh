#!/usr/bin/env bash
set -euo pipefail
export CAMPAIGN_ID=qwen38-gdn0-packaged-prefill-pad512-20260831-d37
export TARGET_LAYER=0
export TARGET_CALL=2
export TRACE_HOOK_NAME=qwen38-gdn-stage-trace-sitecustomize.py
export TRACE_IMAGE=neural-download/vllm-openai-xpu:qwen38-autoround-gdn-int4-prefill-pad512-r2
export TRACE_IMAGE_ID=sha256:628168f33e6bdc05b144e49d14a31b8edf3a189201a4643c9f5ad95512f0dd24
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-gdn-int4-prefill-pad512-d37-prereg.md
exec bash "$(dirname "$0")/run-qwen38-decoder-layer-trace.sh"
