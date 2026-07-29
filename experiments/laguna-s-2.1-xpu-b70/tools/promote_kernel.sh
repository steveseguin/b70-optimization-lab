#!/usr/bin/env bash
# Promote a built libgrouped_gemm_xe_2.so to the measurement position.
#
# Run this ONLY after an adversary pass returns PROMOTE. It installs the
# binary, mints a runtime lock against the SEALED packet lock, and prints the
# exact environment and campaign command to run. It does not run any leg
# itself, and it refuses to clobber an incumbent it has not first preserved.
set -euo pipefail
umask 077

readonly built="${1:?usage: promote_kernel.sh /path/to/built/libgrouped_gemm_xe_2.so TAG}"
readonly tag="${2:?usage: promote_kernel.sh /path/to/built/libgrouped_gemm_xe_2.so TAG}"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly kernel_tree="${REPRO_KERNEL_TREE:-/home/steve/src/laguna-xpu-kernels-tile12-20260728}"
readonly installed="$kernel_tree/vllm_xpu_kernels/libgrouped_gemm_xe_2.so"
readonly backups="$script_dir/binaries"

[[ -f "$built" ]] || { echo "no such built object: $built" >&2; exit 2; }
mkdir -p -- "$backups"

new_hash="$(sha256sum -- "$built" | cut -d' ' -f1)"
old_hash="$(sha256sum -- "$installed" | cut -d' ' -f1)"

if [[ "$new_hash" == "$old_hash" ]]; then
  echo "built object is already installed ($new_hash); nothing to promote" >&2
  exit 1
fi

# Preserve whatever is currently in the measurement position before touching
# it. A binary that took ~50 minutes to build and is not guaranteed
# byte-reproducible must never exist in only one place.
backup="$backups/libgrouped_gemm_xe_2.so.${old_hash:0:8}-displaced"
if [[ ! -f "$backup" ]]; then
  cp -- "$installed" "$backup"
  [[ "$(sha256sum -- "$backup" | cut -d' ' -f1)" == "$old_hash" ]] \
    || { echo "backup verification failed" >&2; exit 2; }
  echo "preserved displaced binary: $backup"
else
  echo "displaced binary already preserved: $backup"
fi

install -m 0755 -- "$built" "$installed"
[[ "$(sha256sum -- "$installed" | cut -d' ' -f1)" == "$new_hash" ]] \
  || { echo "install verification failed" >&2; exit 2; }
echo "installed: $old_hash -> $new_hash"

lock="$script_dir/runtime-lock-${tag}.json"
python3 "$script_dir/mint_runtime_lock.py" "$installed" "$lock"
lock_hash="$(sha256sum -- "$lock" | cut -d' ' -f1)"

cat <<EOF

--- run the campaign with -------------------------------------------------
export REPRO_KERNEL_TREE=$kernel_tree
export REPRO_VLLM_TREE=/home/steve/src/laguna-vllm-replemb-bf16-20260727
export REPRO_GROUPED_GEMM_SHA256=$new_hash
export REPRO_RUNTIME_LOCK=$lock
export REPRO_RUNTIME_LOCK_SHA256=$lock_hash

$script_dir/laguna_ab_campaign.sh $tag 5 \\
  "pd6|12 11 1 0 0 0 0 0 0 1 1 0 0 '' 64 0 '' 6 0 1 0 ''" \\
  "pd3|12 11 1 0 0 0 0 0 0 1 1 0 0 '' 64 0 '' 3 0 1 0 ''" \\
  "pd12|12 11 1 0 0 0 0 0 0 1 1 0 0 '' 64 0 '' 12 0 1 0 ''"

rollback: install -m 0755 $backup $installed
---------------------------------------------------------------------------
EOF
