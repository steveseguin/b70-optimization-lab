#!/usr/bin/env bash
set -Eeuo pipefail

base=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-piecewise-mtp0-4352.sh
expected_base=533be64e1c7584448c07a5f8895301a32288f4b0472948a91d87235e78c6f09f
ack='RUN qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1'

[[ $# == 3 && "${1:-}" == "--execute" && "${2:-}" == "--ack" && \
   "${3:-}" == "$ack" ]] || {
  printf 'FAIL: graph-anchor attempt-4 wrapper requires the frozen acknowledgement\n' >&2
  exit 2
}
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: graph base launcher hash changed\n' >&2
  exit 1
}
[[ -z "${REASONING_PARSER:-}" ]] || {
  printf 'FAIL: reasoning parser must be absent\n' >&2
  exit 1
}
for forbidden in XPU_GRAPH VLLM_XPU_GRAPH VLLM_XPU_FORCE_GRAPH_WITH_COMM \
  VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE; do
  [[ -z "${!forbidden+x}" ]] || {
    printf 'FAIL: legacy graph control %s must be absent\n' "$forbidden" >&2
    exit 1
  }
done

export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
export VLLM_SRC=/home/steve/src/vllm-current-main
export KERNELS_SRC=/home/steve/src/vllm-xpu-kernels
export VLLM_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm
export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
export CACHE_PARENT=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70
export ATTEMPT=4
export PORT=19678
export MAX_MODEL_LEN=4352
export MTP=0
export MTP_EXACT=0
export KV_CACHE_MEMORY_BYTES=201326592
unset REASONING_PARSER PYTHONOPTIMIZE

exec "$base" "$@"
