#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ack="RUN qwen38-flash-next-fp8-tp4-ep4-eager-mtp1-3072-r1"
if [[ "${1:-}" != "--execute" || "${2:-}" != "--ack" || \
      "${3:-}" != "${ack}" || $# != 3 ]]; then
  printf 'Preregistered wrapper is fail-closed. To run exactly this identity:\n' >&2
  printf '  %q --execute --ack %q\n' "$0" "${ack}" >&2
  exit 2
fi
[[ "${MAX_MODEL_LEN:-3072}" == "3072" ]] || {
  printf 'FAIL: this preregistered wrapper requires MAX_MODEL_LEN=3072\n' >&2
  exit 1
}
[[ "${ATTEMPT:-2}" == "2" ]] || {
  printf 'FAIL: this preregistered wrapper requires ATTEMPT=2\n' >&2
  exit 1
}
[[ "${PORT:-19661}" == "19661" ]] || {
  printf 'FAIL: this preregistered wrapper requires PORT=19661\n' >&2
  exit 1
}
[[ "${MODEL_PATH:-/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8}" == \
   "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8" ]] || {
  printf 'FAIL: this preregistered wrapper requires the verified local NVMe model\n' >&2
  exit 1
}
export MTP=1
export MTP_EXACT=0
export MAX_MODEL_LEN=3072
export ATTEMPT=2
export PORT=19661
export KV_CACHE_MEMORY_BYTES=376569856
export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
exec "${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh" "$@"
