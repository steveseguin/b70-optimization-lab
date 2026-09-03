#!/usr/bin/env bash
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"

readonly vllm_bundle="$repo_root/patches/laguna-s-2.1-xpu-b70/vllm-laguna-width12-dflash-fp8-102tps-record-20260726.bundle"
readonly kernel_bundle="$repo_root/patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-width12-102tps-record-20260726.bundle"
readonly attention_bundle="$repo_root/patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-attention-runtime-906190641-20260726.bundle"
readonly vllm_commit=e596ef1543466ae1a05e5bb8091f58872e2b18ba
readonly kernel_commit=6f9dd3c3a7b1b677a992ca4f431a968408f9c816
readonly attention_commit=906190641d708b8028018c5dde653e265c835348
readonly native_base_commit=4772f727590c51b72add79350b913d098cf67872
readonly xpumem_commit=18a44f440ca3ac2006d5ba19cd12ccca0a0c9982

die() {
  printf 'Laguna source restore: %s\n' "$*" >&2
  exit 2
}

[[ $# == 1 ]] || die "usage: restore-sources.sh DESTINATION"
destination="$(realpath -m -- "$1")"
[[ "$destination" != / && "$destination" != /home && "$destination" != "${HOME:-/home}" ]] \
  || die "refusing broad destination: $destination"
if [[ -e "$destination" ]]; then
  [[ -d "$destination" ]] || die "destination exists and is not a directory"
  [[ -z "$(find "$destination" -mindepth 1 -maxdepth 1 -print -quit)" ]] \
    || die "destination is not empty: $destination"
else
  mkdir -p -- "$destination"
fi

for required in "$vllm_bundle" "$kernel_bundle" "$attention_bundle"; do
  [[ -r "$required" ]] || die "missing bundle: $required"
done

vllm_upstream="${VLLM_UPSTREAM:-https://github.com/vllm-project/vllm.git}"
kernel_upstream="${KERNEL_UPSTREAM:-https://github.com/vllm-project/vllm-xpu-kernels.git}"
vllm_tree="$destination/vllm-record"
kernel_tree="$destination/kernels-record"
attention_tree="$destination/kernels-attention-runtime"
native_base_tree="$destination/kernels-native-base"
xpumem_tree="$destination/kernels-xpumem-source"

git clone --filter=blob:none --no-checkout "$vllm_upstream" "$vllm_tree"
git -C "$vllm_tree" fetch "$vllm_bundle" \
  experiment/laguna-width12-stack-clean-20260726:refs/heads/laguna-record
git -C "$vllm_tree" checkout --detach "$vllm_commit"

git clone --filter=blob:none --no-checkout "$kernel_upstream" "$kernel_tree"
git -C "$kernel_tree" fetch "$kernel_bundle" \
  experiment/laguna-width12-router-clean-20260726:refs/heads/laguna-record
git -C "$kernel_tree" fetch "$attention_bundle" \
  experiment/laguna-s-2.1-fwht-20260721:refs/heads/laguna-attention-runtime
git -C "$kernel_tree" checkout --detach "$kernel_commit"
git -C "$kernel_tree" worktree add --detach "$attention_tree" "$attention_commit"
git -C "$kernel_tree" worktree add --detach "$native_base_tree" "$native_base_commit"
git -C "$kernel_tree" worktree add --detach "$xpumem_tree" "$xpumem_commit"

while IFS=$'\t' read -r tree expected label; do
  actual="$(git -C "$tree" rev-parse HEAD)"
  [[ "$actual" == "$expected" ]] \
    || die "$label commit mismatch: expected $expected, got $actual"
  [[ -z "$(git -C "$tree" status --porcelain --untracked-files=all)" ]] \
    || die "$label worktree is dirty after restore: $tree"
done <<EOF
$vllm_tree	$vllm_commit	vLLM
$kernel_tree	$kernel_commit	kernel-record
$attention_tree	$attention_commit	kernel-attention-runtime
$native_base_tree	$native_base_commit	kernel-native-base
$xpumem_tree	$xpumem_commit	kernel-xpumem-source
EOF

printf 'source_restore=PASS\n'
printf 'vllm_tree=%s\n' "$vllm_tree"
printf 'kernel_tree=%s\n' "$kernel_tree"
printf 'attention_source_tree=%s\n' "$attention_tree"
printf 'native_base_tree=%s\n' "$native_base_tree"
printf 'xpumem_source_tree=%s\n' "$xpumem_tree"
