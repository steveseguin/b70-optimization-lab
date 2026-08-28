#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base_launcher="${script_dir}/launch-tp4-ep4-eager-mtp2-long-context-base.sh"
expected_base=f276f933c6949b0236e0f013596ac91f5089c0a6777ab2cb1bac012a4f652386
[[ "$(sha256sum "$base_launcher" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: frozen MTP2 long-context base hash mismatch\n' >&2
  exit 1
}
[[ "${MODEL_PATH:-/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8}" == \
   /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8 ]] || { printf 'FAIL: frozen model path required\n' >&2; exit 1; }
[[ "${MAX_MODEL_LEN:-16512}" == 16512 ]] || { printf 'FAIL: MAX_MODEL_LEN must be 16512\n' >&2; exit 1; }
[[ "${ATTEMPT:-1}" == 1 ]] || { printf 'FAIL: ATTEMPT must be 1\n' >&2; exit 1; }
[[ "${PORT:-19680}" == 19680 ]] || { printf 'FAIL: PORT must be 19680\n' >&2; exit 1; }
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
export MTP=2 MTP_EXACT=0 MAX_MODEL_LEN=16512 ATTEMPT=1 PORT=19680
export KV_CACHE_MEMORY_BYTES=470712320
export REASONING_PARSER=
unset PYTHONOPTIMIZE
exec "$base_launcher" "$@"
