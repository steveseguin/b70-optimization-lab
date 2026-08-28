#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base_launcher="${script_dir}/launch-tp4-ep4-eager-mtp2-long-context-scheduler32-base.sh"
expected_base=66530afb827d0129b85ebec89e21d5ce7361b315ab7bbda0238043ed0fb730c7
[[ "$(sha256sum "$base_launcher" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: frozen MTP2 scheduler32 base hash mismatch\n' >&2
  exit 1
}
[[ "${MODEL_PATH:-/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8}" == \
   /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8 ]] || { printf 'FAIL: frozen model path required\n' >&2; exit 1; }
[[ "${MAX_MODEL_LEN:-16512}" == 16512 ]] || { printf 'FAIL: MAX_MODEL_LEN must be 16512\n' >&2; exit 1; }
[[ "${MAX_NUM_BATCHED_TOKENS:-32}" == 32 ]] || { printf 'FAIL: MAX_NUM_BATCHED_TOKENS must be 32\n' >&2; exit 1; }
[[ "${ATTEMPT:-2}" == 2 ]] || { printf 'FAIL: ATTEMPT must be 2\n' >&2; exit 1; }
[[ "${PORT:-19683}" == 19683 ]] || { printf 'FAIL: PORT must be 19683\n' >&2; exit 1; }
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
export MTP=2 MTP_EXACT=0 MAX_MODEL_LEN=16512 MAX_NUM_BATCHED_TOKENS=32
export ATTEMPT=2 PORT=19683 KV_CACHE_MEMORY_BYTES=470712320
export REASONING_PARSER=
unset PYTHONOPTIMIZE VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS
exec "$base_launcher" "$@"
