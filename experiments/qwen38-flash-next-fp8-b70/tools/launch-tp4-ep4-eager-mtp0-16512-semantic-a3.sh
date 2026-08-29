#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base_launcher="${script_dir}/launch-tp4-ep4-eager-mtp0-long-context-base.sh"
expected_base=d5ccc4d52220f7ef46f19202436edf56e0c40f125b1b807c84125df18093b5c1
[[ "$(sha256sum "$base_launcher" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: frozen long-context base launcher hash mismatch\n' >&2
  exit 1
}

phase=${A3_PHASE:-}
case "$phase" in
  1) attempt=3; port=19675 ;;
  2) attempt=4; port=19676 ;;
  *) printf 'FAIL: A3_PHASE must be exactly 1 or 2\n' >&2; exit 1 ;;
esac

model=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8
[[ "${MODEL_PATH:-$model}" == "$model" ]] || { printf 'FAIL: frozen external model path required\n' >&2; exit 1; }
[[ "${MAX_MODEL_LEN:-16512}" == 16512 ]] || { printf 'FAIL: MAX_MODEL_LEN must be 16512\n' >&2; exit 1; }
[[ "${ATTEMPT:-$attempt}" == "$attempt" ]] || { printf 'FAIL: phase/attempt mismatch\n' >&2; exit 1; }
[[ "${PORT:-$port}" == "$port" ]] || { printf 'FAIL: phase/port mismatch\n' >&2; exit 1; }

export MODEL_PATH="$model"
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
export VLLM_SRC=/home/steve/src/vllm-current-main
export KERNELS_SRC=/home/steve/src/vllm-xpu-kernels
export VLLM_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm
export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
export CACHE_PARENT=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70
export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=16512 ATTEMPT="$attempt" PORT="$port"
export KV_CACHE_MEMORY_BYTES=358465536
export REASONING_PARSER=
unset PYTHONOPTIMIZE
exec "$base_launcher" "$@"
