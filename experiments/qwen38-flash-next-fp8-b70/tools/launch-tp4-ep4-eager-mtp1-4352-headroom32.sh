#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ "${MAX_MODEL_LEN:-4352}" == "4352" ]] || {
  printf 'FAIL: this preregistered wrapper requires MAX_MODEL_LEN=4352\n' >&2
  exit 1
}
[[ "${ATTEMPT:-1}" == "1" ]] || {
  printf 'FAIL: this preregistered wrapper requires ATTEMPT=1\n' >&2
  exit 1
}
[[ "${PORT:-19644}" == "19644" ]] || {
  printf 'FAIL: this preregistered wrapper requires PORT=19644\n' >&2
  exit 1
}
export MTP=1
export MTP_EXACT=0
export MAX_MODEL_LEN=4352
export ATTEMPT=1
export PORT=19644
export KV_CACHE_MEMORY_BYTES=376569856
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
exec "${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh" "$@"
