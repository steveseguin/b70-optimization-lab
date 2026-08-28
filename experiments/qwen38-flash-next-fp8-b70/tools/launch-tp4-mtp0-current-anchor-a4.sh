#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh"
expected_base=62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7

[[ $# == 3 && "${1:-}" == "--execute" && "${2:-}" == "--ack" && \
   "${3:-}" == "RUN qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1" ]] || {
  printf 'FAIL: current-anchor wrapper requires the frozen launcher acknowledgement\n' >&2
  exit 2
}
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: base launcher hash changed\n' >&2
  exit 1
}
[[ -z "${REASONING_PARSER:-}" ]] || {
  printf 'FAIL: reasoning parser must be absent for this direct-answer anchor\n' >&2
  exit 1
}

export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
export VLLM_SRC=/home/steve/src/vllm-current-main
export KERNELS_SRC=/home/steve/src/vllm-xpu-kernels
export VLLM_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm
export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
export CACHE_PARENT=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70
export ATTEMPT=4
export PORT=19673
export MAX_MODEL_LEN=4352
export MTP=0
export MTP_EXACT=0
export KV_CACHE_MEMORY_BYTES=201326592
unset REASONING_PARSER PYTHONOPTIMIZE

exec "$base" "$@"

