#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ "${MAX_MODEL_LEN:-4352}" == "4352" ]] || {
  printf 'FAIL: this preregistered wrapper requires MAX_MODEL_LEN=4352\n' >&2
  exit 1
}
[[ "${ATTEMPT:-2}" == "2" ]] || {
  printf 'FAIL: this preregistered wrapper requires ATTEMPT=2\n' >&2
  exit 1
}
[[ "${PORT:-19647}" == "19647" ]] || {
  printf 'FAIL: this preregistered wrapper requires PORT=19647\n' >&2
  exit 1
}
[[ "${REASONING_PARSER:-qwen3}" == "qwen3" ]] || {
  printf 'FAIL: this preregistered wrapper requires REASONING_PARSER=qwen3\n' >&2
  exit 1
}
[[ "${MODEL_PATH:-/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8}" == "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8" ]] || {
  printf 'FAIL: this preregistered wrapper requires the verified local model path\n' >&2
  exit 1
}
export MTP=3
export MTP_EXACT=0
export MAX_MODEL_LEN=4352
export ATTEMPT=2
export PORT=19647
export KV_CACHE_MEMORY_BYTES=294195200
export REASONING_PARSER=qwen3
export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
exec "${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh" "$@"
