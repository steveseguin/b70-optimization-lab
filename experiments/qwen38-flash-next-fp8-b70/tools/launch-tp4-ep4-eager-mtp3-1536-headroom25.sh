#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ack="RUN qwen38-flash-next-fp8-tp4-ep4-eager-mtp3-1536-r1"
if [[ "${1:-}" != "--execute" || "${2:-}" != "--ack" || \
      "${3:-}" != "${ack}" || $# != 3 ]]; then
  printf 'Preregistered wrapper is fail-closed. To run exactly this identity:\n' >&2
  printf '  %q --execute --ack %q\n' "$0" "${ack}" >&2
  exit 2
fi
[[ "${MAX_MODEL_LEN:-1536}" == "1536" ]] || {
  printf 'FAIL: this preregistered wrapper requires MAX_MODEL_LEN=1536\n' >&2
  exit 1
}
[[ "${ATTEMPT:-1}" == "1" ]] || {
  printf 'FAIL: this preregistered wrapper requires ATTEMPT=1\n' >&2
  exit 1
}
[[ "${PORT:-19663}" == "19663" ]] || {
  printf 'FAIL: this preregistered wrapper requires PORT=19663\n' >&2
  exit 1
}
[[ "${MODEL_PATH:-/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8}" == \
   "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8" ]] || {
  printf 'FAIL: this preregistered wrapper requires the verified local NVMe model\n' >&2
  exit 1
}
[[ -z "${REASONING_PARSER:-}" ]] || {
  printf 'FAIL: this preregistered wrapper requires REASONING_PARSER to be absent\n' >&2
  exit 1
}
[[ "${VLLM_SRC:-/home/steve/src/vllm-current-main}" == \
   "/home/steve/src/vllm-current-main" ]] || {
  printf 'FAIL: this preregistered wrapper requires the frozen vLLM checkout path\n' >&2
  exit 1
}
[[ "${KERNELS_SRC:-/home/steve/src/vllm-xpu-kernels}" == \
   "/home/steve/src/vllm-xpu-kernels" ]] || {
  printf 'FAIL: this preregistered wrapper requires the frozen kernels checkout path\n' >&2
  exit 1
}
[[ "${VLLM_PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}" == \
   "/home/steve/.venvs/vllm-xpu/bin/python" ]] || {
  printf 'FAIL: this preregistered wrapper requires the frozen vLLM interpreter\n' >&2
  exit 1
}
[[ "${VLLM_BIN:-/home/steve/.venvs/vllm-xpu/bin/vllm}" == \
   "/home/steve/.venvs/vllm-xpu/bin/vllm" ]] || {
  printf 'FAIL: this preregistered wrapper requires the frozen vLLM executable\n' >&2
  exit 1
}
[[ "${RUN_PARENT:-/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70}" == \
   "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70" ]] || {
  printf 'FAIL: this preregistered wrapper requires the frozen result parent\n' >&2
  exit 1
}
[[ "${CACHE_PARENT:-/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70}" == \
   "/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70" ]] || {
  printf 'FAIL: this preregistered wrapper requires the frozen cache parent\n' >&2
  exit 1
}
export MTP=3
export MTP_EXACT=0
export MAX_MODEL_LEN=1536
export ATTEMPT=1
export PORT=19663
export KV_CACHE_MEMORY_BYTES=294195200
export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
export REASONING_PARSER=
export VLLM_SRC=/home/steve/src/vllm-current-main
export KERNELS_SRC=/home/steve/src/vllm-xpu-kernels
export VLLM_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm
export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
export CACHE_PARENT=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70
exec "${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh" "$@"
