#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../../.." && pwd)
source_packet="$repo/patches/qwen36-27b-autoround-int4-b70/record-20260711"
destination=${1:-}

if [[ -z "$destination" || $# -ne 1 ]]; then
  printf 'usage: %s DESTINATION\n' "$0" >&2
  exit 2
fi
if [[ -e "$destination" ]]; then
  printf 'destination already exists: %s\n' "$destination" >&2
  exit 2
fi

vllm_remote=${VLLM_REMOTE:-https://github.com/vllm-project/vllm.git}
kernels_remote=${VLLM_XPU_KERNELS_REMOTE:-https://github.com/vllm-project/vllm-xpu-kernels.git}

restore_one() {
  local name=$1
  local remote=$2
  local prerequisite=$3
  local recorded_head=$4
  local bundle=$5
  local patch=$6
  local patch_sha=$7
  local tree="$destination/$name"

  git clone --filter=blob:none --no-checkout "$remote" "$tree"
  git -C "$tree" fetch --no-tags origin "$prerequisite"
  git -C "$tree" checkout --detach "$prerequisite"
  git -C "$tree" bundle verify "$bundle"
  git -C "$tree" fetch --no-tags "$bundle" HEAD
  git -C "$tree" checkout --detach FETCH_HEAD

  actual_head=$(git -C "$tree" rev-parse HEAD)
  if [[ "$actual_head" != "$recorded_head" ]]; then
    printf '%s head mismatch: expected %s, got %s\n' \
      "$name" "$recorded_head" "$actual_head" >&2
    exit 3
  fi

  actual_patch_sha=$(sha256sum "$patch" | awk '{print $1}')
  if [[ "$actual_patch_sha" != "$patch_sha" ]]; then
    printf '%s patch checksum mismatch\n' "$name" >&2
    exit 3
  fi
  git -C "$tree" apply --check "$patch"
  git -C "$tree" apply "$patch"

  restored_patch_sha=$(git -C "$tree" diff --binary | sha256sum | awk '{print $1}')
  if [[ "$restored_patch_sha" != "$patch_sha" ]]; then
    printf '%s restored diff mismatch: expected %s, got %s\n' \
      "$name" "$patch_sha" "$restored_patch_sha" >&2
    exit 3
  fi

  if [[ -n "$(git -C "$tree" ls-files --others --exclude-standard)" ]]; then
    printf '%s restore unexpectedly created untracked files\n' "$name" >&2
    exit 3
  fi
  printf '%s restored at detached %s + working patch %s\n' \
    "$name" "$recorded_head" "$patch_sha"
}

mkdir -p -- "$destination"

restore_one \
  vllm \
  "$vllm_remote" \
  c51df43005726a09c6eb7348e8c1b00501c70a8e \
  e7213ba8e13b74d7bfa3cbc05435a45df90eb76a \
  "$source_packet/vllm-record-commits.bundle" \
  "$source_packet/vllm-final-working.patch" \
  dcf84454f64bdeca546aa1697f4cd6af89fa95bb56f80ed314ad4d364e134b24

restore_one \
  vllm-xpu-kernels \
  "$kernels_remote" \
  28e1f5e74c15744b69cf3b760f6160ceabd15de0 \
  3b4effeeffd83f6ef4696bbe7e76d924a0e9d171 \
  "$source_packet/vllm-xpu-kernels-record-commits.bundle" \
  "$source_packet/vllm-xpu-kernels-final-working.patch" \
  edcb9314b43d6990474dfb5d64e3716e8d4c33618ec0e3fbd11ae671e47c8c1f

printf 'Source restoration complete under %s\n' "$destination"
