#!/usr/bin/env bash
# Interleaved campaign ACROSS binaries, one binary swapped in per leg.
#
# Comparing across binaries is normally forbidden here, because codegen
# differences confound a selector comparison. It is required in exactly one
# case: when the change under test IS a codegen change, so "does shipping this
# help" cannot be answered within a single binary.
#
# The confound is handled by round-robin interleaving at leg granularity rather
# than by running each binary in a block. Every arm sees the same drift, the
# same thermal state and the same ordering effects, because arm k of round r is
# always followed by arm k+1 of round r.
#
# usage: laguna_xbin_campaign.sh TAG N "LABEL|SO|LOCK|<leg args 4..25>" ...
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$script_dir/laguna_nvme_paths.sh"

readonly tag="${1:?usage: laguna_xbin_campaign.sh TAG N \"LABEL|SO|LOCK|args\" ...}"
readonly rounds="${2:?usage: laguna_xbin_campaign.sh TAG N \"LABEL|SO|LOCK|args\" ...}"
shift 2
(( $# >= 1 )) || { echo "need at least one arm spec" >&2; exit 2; }
readonly arms=("$@")

readonly leg="$script_dir/run_laguna_replemb_measurement_leg.sh"
readonly kernel_tree="${REPRO_KERNEL_TREE:-/home/steve/src/laguna-xpu-kernels-tile12-20260728}"
readonly installed="$kernel_tree/vllm_xpu_kernels/libgrouped_gemm_xe_2.so"
export REPRO_KERNEL_TREE
export REPRO_VLLM_TREE="${REPRO_VLLM_TREE:-/home/steve/src/laguna-vllm-replemb-bf16-20260727}"

# Validate every arm up front. Discovering a bad path midway through a
# two-hour campaign wastes the legs already run.
for spec in "${arms[@]}"; do
  IFS='|' read -r label so lock _ <<<"$spec"
  [[ -f "$so"   ]] || { echo "arm $label: no such .so: $so" >&2; exit 2; }
  [[ -f "$lock" ]] || { echo "arm $label: no such lock: $lock" >&2; exit 2; }
  printf 'arm %-6s so=%s lock=%s\n' "$label" \
    "$(sha256sum -- "$so"   | cut -c1-16)" "$(sha256sum -- "$lock" | cut -c1-16)"
done
echo

for (( round = 1; round <= rounds; round++ )); do
  for spec in "${arms[@]}"; do
    IFS='|' read -r label so lock args <<<"$spec"
    so_hash="$(sha256sum -- "$so" | cut -d' ' -f1)"

    # Swap the binary in and prove it landed before spending seven minutes on
    # a leg that would otherwise silently measure the previous arm.
    if [[ "$(sha256sum -- "$installed" | cut -d' ' -f1)" != "$so_hash" ]]; then
      install -m 0755 -- "$so" "$installed"
      [[ "$(sha256sum -- "$installed" | cut -d' ' -f1)" == "$so_hash" ]] \
        || { echo "install of $so did not take" >&2; exit 2; }
    fi

    export REPRO_GROUPED_GEMM_SHA256="$so_hash"
    export REPRO_RUNTIME_LOCK="$lock"
    export REPRO_RUNTIME_LOCK_SHA256="$(sha256sum -- "$lock" | cut -d' ' -f1)"

    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    run_dir="$LAGUNA_NVME_RUN_ROOT/${tag}-${label}-r${round}-${stamp}"
    echo "=== $tag $label round $round  (so ${so_hash:0:12}) -> $run_dir"

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
