#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
env \
  PREREG_PATH="${repo}/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-gemma-rms-cross-process-d3b-prereg.md" \
  RESULT_ROOT=/mnt/fast-ai/bench-results/qwen38-gemma-rms-cross-process-20260831-d3b \
  "${script_dir}/run-20260831-qwen38-gemma-rms-cross-process-d3.sh"
