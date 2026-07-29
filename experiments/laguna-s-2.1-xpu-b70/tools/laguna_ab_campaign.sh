#!/usr/bin/env bash
# Interleaved A/B(/C...) endpoint campaign on ONE binary.
#
# Every arm runs against the same installed libgrouped_gemm_xe_2.so, the same
# runtime lock, and the same leg script. Arms differ only in the selector
# values passed as leg arguments. Rounds are round-robin, so drift hits every
# arm equally: A B A B A B ...  Never compare across binaries.
#
# usage: laguna_ab_campaign.sh TAG N "LABEL|<leg args 4..25>" "LABEL|<...>" ...
#
# The per-arm argument string is leg-script positional arguments 4 through 25:
#   M SPEC METADATA DRAFTGRAPH FUSIONS QKNORM LOCAL_ARGMAX CAPTURE_ATTN
#   INLINE_ATTN WIDTH12_STACK DFLASH_FP8 REPLEMB DRAFT_PROBE EVENT_PROFILE_ROOT
#   W1_N_TILE LOG_MOE_ROWS MXFP4_SMALL_M_N PREFETCH_DIST SCALE_FOLD SCALE_VEC
#   DEQUANT_MAD SCALE_HOIST
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$script_dir/laguna_nvme_paths.sh"

readonly tag="${1:?usage: laguna_ab_campaign.sh TAG N \"LABEL|args\" ...}"
readonly rounds="${2:?usage: laguna_ab_campaign.sh TAG N \"LABEL|args\" ...}"
shift 2
(( $# >= 1 )) || { echo "need at least one arm spec" >&2; exit 2; }
readonly arms=("$@")

readonly leg="$script_dir/run_laguna_replemb_measurement_leg.sh"
readonly lock_file="${LAGUNA_GPU_LOCK:-}"

# Identity of the binary under test. Every arm shares it; that is the point.
export REPRO_KERNEL_TREE="${REPRO_KERNEL_TREE:-/home/steve/src/laguna-xpu-kernels-tile12-20260728}"
export REPRO_VLLM_TREE="${REPRO_VLLM_TREE:-/home/steve/src/laguna-vllm-replemb-bf16-20260727}"

gg_so="$REPRO_KERNEL_TREE/vllm_xpu_kernels/libgrouped_gemm_xe_2.so"
[[ -f "$gg_so" ]] || { echo "missing $gg_so" >&2; exit 2; }
export REPRO_GROUPED_GEMM_SHA256="${REPRO_GROUPED_GEMM_SHA256:-$(sha256sum -- "$gg_so" | cut -d' ' -f1)}"
[[ -n "${REPRO_RUNTIME_LOCK:-}" ]] || { echo "REPRO_RUNTIME_LOCK must be set" >&2; exit 2; }
export REPRO_RUNTIME_LOCK
export REPRO_RUNTIME_LOCK_SHA256="${REPRO_RUNTIME_LOCK_SHA256:-$(sha256sum -- "$REPRO_RUNTIME_LOCK" | cut -d' ' -f1)}"

echo "campaign      : $tag"
echo "rounds        : $rounds"
echo "arms          : ${#arms[@]}"
echo "kernel tree   : $REPRO_KERNEL_TREE"
echo "vllm tree     : $REPRO_VLLM_TREE"
echo "grouped_gemm  : $REPRO_GROUPED_GEMM_SHA256"
echo "runtime lock  : $REPRO_RUNTIME_LOCK ($REPRO_RUNTIME_LOCK_SHA256)"
echo "leg script    : $(sha256sum -- "$leg" | cut -d' ' -f1)"
echo

for (( round = 1; round <= rounds; round++ )); do
  for spec in "${arms[@]}"; do
    label="${spec%%|*}"
    args="${spec#*|}"
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    run_dir="$LAGUNA_NVME_RUN_ROOT/${tag}-${label}-r${round}-${stamp}"
    echo "=== $tag $label round $round -> $run_dir"
    # Arm specs are re-parsed with the shell's own quoting rules rather than
    # split on whitespace. Several leg arguments -- EVENT_PROFILE_ROOT (17),
    # MXFP4_SMALL_M_N (20), SCALE_HOIST (25) -- are legitimately empty, and
    # plain word splitting turns '' into a literal two-character token. That
    # would hand the leg a non-empty junk value for the event-profile root and
    # switch profiling on inside a scored measurement.
    unset argv
    eval "argv=($args)"
    if "$leg" candidate B2 "$run_dir" "${argv[@]}"; then
      status="$(cat "$run_dir/status.txt" 2>/dev/null || echo 'status=MISSING')"
      metric="$(cat "$run_dir/metric-accounting.stdout" 2>/dev/null || echo 'metric=MISSING')"
      echo "--- $label round $round: $status"
      echo "$metric"
    else
      echo "--- $label round $round: LEG FAILED (exit $?)" >&2
    fi
    echo
  done
done

echo "campaign $tag complete; summarize with laguna_ab_summarize.py $tag"
