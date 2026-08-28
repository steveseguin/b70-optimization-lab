#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-ep4-eager-mtp0-vision-512-base.sh"
expected_base=487f088481c0c7f5e821bdce7dda41bb20aa0761c4453215a0662f23473beb46
ack='RUN qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1'

[[ $# == 3 && "${1:-}" == "--execute" && "${2:-}" == "--ack" && \
   "${3:-}" == "$ack" ]] || {
  printf 'FAIL: vision attempt-6 wrapper requires the frozen acknowledgement\n' >&2
  exit 2
}
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: vision base launcher hash changed\n' >&2
  exit 1
}
for forbidden in REASONING_PARSER PYTHONOPTIMIZE XPU_GRAPH VLLM_XPU_GRAPH \
  VLLM_XPU_FORCE_GRAPH_WITH_COMM VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE \
  VLLM_PLE_CPU_OFFLOAD; do
  [[ -z "${!forbidden+x}" ]] || {
    printf 'FAIL: inherited control %s must be absent\n' "$forbidden" >&2
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
export ATTEMPT=6
export PORT=19685
export MAX_MODEL_LEN=512
export MTP=0
export MTP_EXACT=0
export KV_CACHE_MEMORY_BYTES=201326592
export COMPILE_CACHE_DIR=/tmp/q38v-a6-c
export RPC_DIR=/tmp/q38v-a6-r
unset REASONING_PARSER PYTHONOPTIMIZE

exec "$base" "$@"
