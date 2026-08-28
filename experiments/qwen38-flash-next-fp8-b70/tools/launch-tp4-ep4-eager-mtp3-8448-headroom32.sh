#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base_launcher="${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh"
expected_base=62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7
[[ "$(sha256sum "$base_launcher" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: frozen base launcher hash mismatch\n' >&2
  exit 1
}
[[ "${MODEL_PATH:-/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8}" == \
   /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8 ]] || { printf 'FAIL: frozen model path required\n' >&2; exit 1; }
[[ "${MAX_MODEL_LEN:-8448}" == 8448 ]] || { printf 'FAIL: MAX_MODEL_LEN must be 8448\n' >&2; exit 1; }
[[ "${ATTEMPT:-1}" == 1 ]] || { printf 'FAIL: ATTEMPT must be 1\n' >&2; exit 1; }
[[ "${PORT:-19669}" == 19669 ]] || { printf 'FAIL: PORT must be 19669\n' >&2; exit 1; }
[[ "${RUN_PARENT:-/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70}" == \
   /mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70 ]] || { printf 'FAIL: frozen result parent required\n' >&2; exit 1; }
[[ "${CACHE_PARENT:-/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70}" == \
   /mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70 ]] || { printf 'FAIL: frozen cache parent required\n' >&2; exit 1; }

export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
export VLLM_SRC=/home/steve/src/vllm-current-main
export KERNELS_SRC=/home/steve/src/vllm-xpu-kernels
export VLLM_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm
export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
export CACHE_PARENT=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70
export MTP=3 MTP_EXACT=0 MAX_MODEL_LEN=8448 ATTEMPT=1 PORT=19669
export KV_CACHE_MEMORY_BYTES=376569856
export REASONING_PARSER=
unset PYTHONOPTIMIZE
exec "$base_launcher" "$@"
