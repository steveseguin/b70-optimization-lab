#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ "${MAX_MODEL_LEN:-512}" == "512" ]] || {
  printf 'FAIL: this preregistered wrapper requires MAX_MODEL_LEN=512\n' >&2
  exit 1
}
[[ "${ATTEMPT:-2}" == "2" ]] || {
  printf 'FAIL: this preregistered wrapper requires ATTEMPT=2\n' >&2
  exit 1
}
export MTP=3
export MTP_EXACT=0
export MAX_MODEL_LEN=512
export ATTEMPT=2
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
exec "${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh" "$@"
