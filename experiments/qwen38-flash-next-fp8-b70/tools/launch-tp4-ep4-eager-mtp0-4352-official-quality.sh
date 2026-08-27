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
[[ "${PORT:-19646}" == "19646" ]] || {
  printf 'FAIL: this preregistered wrapper requires PORT=19646\n' >&2
  exit 1
}
[[ "${REASONING_PARSER:-qwen3}" == "qwen3" ]] || {
  printf 'FAIL: this preregistered wrapper requires REASONING_PARSER=qwen3\n' >&2
  exit 1
}
export MTP=0
export MTP_EXACT=0
export MAX_MODEL_LEN=4352
export ATTEMPT=2
export PORT=19646
export KV_CACHE_MEMORY_BYTES=201326592
export REASONING_PARSER=qwen3
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
exec "${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh" "$@"
