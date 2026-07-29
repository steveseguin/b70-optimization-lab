#!/usr/bin/env bash
# Interleaved campaign across BINARIES, one self-consistent tree per arm.
#
# Comparing across binaries is normally forbidden here, because codegen
# differences confound a selector comparison. It is required in exactly one
# case: when the change under test IS a codegen change, so "does shipping this
# help" cannot be answered inside a single binary.
#
# Two properties make it defensible:
#
#  * Interleaving at LEG granularity, not in blocks. Arm k of round r is always
#    followed by arm k+1 of round r, so drift, thermal state and ordering hit
#    every arm equally.
#  * One checked-out tree per binary, rather than swapping a .so into a shared
#    tree. The leg script stamps `kernel_commit` from the tree's HEAD and never
#    validates it against the binary, so a swapped .so would record the wrong
#    provenance. Giving each arm its own tree keeps commit and binary agreeing,
#    and removes the per-leg install that could otherwise fail and silently
#    measure the previous arm.
#
# usage: laguna_xbin_campaign.sh TAG N "LABEL|TREE|LOCK|<leg args 4..25>" ...
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$script_dir/laguna_nvme_paths.sh"

readonly tag="${1:?usage: laguna_xbin_campaign.sh TAG N \"LABEL|TREE|LOCK|args\" ...}"
readonly rounds="${2:?usage: laguna_xbin_campaign.sh TAG N \"LABEL|TREE|LOCK|args\" ...}"
shift 2
(( $# >= 1 )) || { echo "need at least one arm spec" >&2; exit 2; }
readonly arms=("$@")

readonly leg="$script_dir/run_laguna_replemb_measurement_leg.sh"
export REPRO_VLLM_TREE="${REPRO_VLLM_TREE:-/home/steve/src/laguna-vllm-replemb-bf16-20260727}"

# Validate every arm before the first leg. Discovering a bad path midway
# through a two-hour campaign wastes everything already run.
for spec in "${arms[@]}"; do
  IFS='|' read -r label tree lock _ <<<"$spec"
  so="$tree/vllm_xpu_kernels/libgrouped_gemm_xe_2.so"
  [[ -d "$tree" ]] || { echo "arm $label: no such tree: $tree" >&2; exit 2; }
  [[ -f "$so"   ]] || { echo "arm $label: no grouped_gemm in $tree" >&2; exit 2; }
  [[ -f "$lock" ]] || { echo "arm $label: no such lock: $lock" >&2; exit 2; }
  printf 'arm %-9s commit=%s so=%s lock=%s\n' "$label" \
    "$(git -C "$tree" rev-parse --short HEAD)" \
    "$(sha256sum -- "$so"   | cut -c1-16)" \
    "$(sha256sum -- "$lock" | cut -c1-16)"
done
echo

for (( round = 1; round <= rounds; round++ )); do
  for spec in "${arms[@]}"; do
    IFS='|' read -r label tree lock args <<<"$spec"
    so="$tree/vllm_xpu_kernels/libgrouped_gemm_xe_2.so"

    export REPRO_KERNEL_TREE="$tree"
    export REPRO_GROUPED_GEMM_SHA256="$(sha256sum -- "$so" | cut -d' ' -f1)"
    export REPRO_RUNTIME_LOCK="$lock"
    export REPRO_RUNTIME_LOCK_SHA256="$(sha256sum -- "$lock" | cut -d' ' -f1)"

    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    run_dir="$LAGUNA_NVME_RUN_ROOT/${tag}-${label}-r${round}-${stamp}"
    echo "=== $tag $label round $round  (${REPRO_GROUPED_GEMM_SHA256:0:12}) -> $run_dir"

    unset argv
    eval "argv=($args)"
    if "$leg" candidate B2 "$run_dir" "${argv[@]}"; then
      echo "--- $label round $round: $(cat "$run_dir/status.txt" 2>/dev/null || echo MISSING)"
      cat "$run_dir/metric-accounting.stdout" 2>/dev/null || true
    else
      echo "--- $label round $round: LEG FAILED" >&2
    fi
    echo
  done
done

echo "campaign $tag complete; summarize with laguna_ab_summarize.py $tag"
