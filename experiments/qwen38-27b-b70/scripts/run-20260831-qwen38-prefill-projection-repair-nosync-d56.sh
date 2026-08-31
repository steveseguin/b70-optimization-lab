#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$script_dir/../../.." && pwd)
export CAMPAIGN_ID=qwen38-prefill-projection-repair-nosync-20260831-d56
export TARGET_LAYER=63
export TARGET_CALL=2
export TRACE_HOOK_NAME=qwen38-import-repair-all-decoder-trace-sitecustomize.py
export TRACE_IMAGE=neural-download/vllm-openai-xpu:qwen38-autoround-gdn-int4-prefill-pad512-r1
export TRACE_IMAGE_ID=sha256:03da963d9d9b3b2cfc5cb7d9f1bc0aeb9ebd7e1b9495e3cad4e5b9e5dd4fc493
export REPAIR_MODULE_PATH="$repo/repro/qwen38-27b-autoround-int4-b70/patches/qwen38-prefill-projection-repair-sitecustomize.py"
export VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE=0
export PREREG_PATH=experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-prefill-projection-repair-nosync-d56-prereg.md
exec bash "$script_dir/run-qwen38-decoder-layer-trace.sh"
