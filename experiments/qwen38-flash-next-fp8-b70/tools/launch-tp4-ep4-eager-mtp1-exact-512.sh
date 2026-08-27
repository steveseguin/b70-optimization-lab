#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ "${MAX_MODEL_LEN:-512}" == "512" ]] || {
  printf 'FAIL: this preregistered wrapper requires MAX_MODEL_LEN=512\n' >&2
  exit 1
}
[[ "${ATTEMPT:-3}" == "3" ]] || {
  printf 'FAIL: this preregistered wrapper requires ATTEMPT=3\n' >&2
  exit 1
}
export MTP=1
export MTP_EXACT=1
export MAX_MODEL_LEN=512
export ATTEMPT=3
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-mtp1-exact-ad25aa9-b70
exec "${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh" "$@"
