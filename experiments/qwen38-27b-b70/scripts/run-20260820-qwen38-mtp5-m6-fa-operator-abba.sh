#!/usr/bin/env bash
set -euo pipefail

# Fresh-process, exact-shape FlashAttention operator ABBA on B70 devices 2,3.
# This screen never starts vLLM and does not authorize a full-25 run by itself.

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
driver=$(realpath -- "$0")
operator="$repo/experiments/qwen38-27b-b70/scripts/qwen38_mtp5_m6_fa_operator.py"
python=/home/steve/.venvs/vllm-xpu/bin/python
control_stage=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
torch_lib=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib
venv_lib=/home/steve/.venvs/vllm-xpu/lib
operator_sha=0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f
action=${1:-}

usage() {
  printf 'usage: %s check CANDIDATE_STAGE_MANIFEST | run CANDIDATE_STAGE_MANIFEST OUTPUT_ROOT | compare OUTPUT_ROOT\n' "$0" >&2
  exit 2
}

case "$action" in
  check)
    [[ $# -eq 2 ]] || usage
    candidate_manifest=$2
    ;;
  run)
    [[ $# -eq 3 ]] || usage
    candidate_manifest=$2
    output_root=$3
    ;;
  compare)
    [[ $# -eq 2 ]] || usage
    output_root=$2
    candidate_manifest=
    ;;
  *) usage ;;
esac

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 3
}

verify_sha() {
  local path=$1 expected=$2 label=$3 actual
  [[ -f "$path" ]] || fail "$label missing: $path"
  actual=$(sha256sum -- "$path" | awk '{print $1}')
  [[ "$actual" == "$expected" ]] || \
    fail "$label SHA mismatch: actual=$actual expected=$expected"
}

[[ "$(git -C "$repo" branch --show-current)" == main ]] || fail 'requires main'
[[ -z "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]] || \
  fail 'requires a clean lab repository'
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || \
  fail 'requires local main == origin/main'
[[ -x "$python" ]] || fail "missing XPU Python: $python"
verify_sha "$operator" "$operator_sha" operator-qualifier
repo_head=$(git -C "$repo" rev-parse HEAD)
driver_sha=$(sha256sum -- "$driver" | awk '{print $1}')

if [[ "$action" == check || "$action" == run ]]; then
  [[ -f "$candidate_manifest" ]] || fail "missing candidate manifest: $candidate_manifest"
  candidate_manifest=$(realpath -- "$candidate_manifest")
  "$python" "$operator" validate-stage --role control --stage "$control_stage" >/dev/null
  "$python" "$operator" validate-stage --role candidate \
    --stage-manifest "$candidate_manifest" >/dev/null
  candidate_stage=$(jq -er '.stage | select(type == "string")' "$candidate_manifest") || \
    fail 'candidate manifest has no string stage'
  [[ "$candidate_stage" == "$(realpath -- "$candidate_stage")" ]] || \
    fail 'candidate stage is not canonical'
fi

if [[ "$action" == check ]]; then
  discovery=$(xpu-smi discovery 2>&1) || fail 'xpu-smi discovery failed'
  [[ $(grep -c 'Arc(TM) Pro B70' <<<"$discovery" || true) -eq 4 ]] || \
    fail 'expected exactly four Intel Arc Pro B70 devices'
  printf 'PASS: exact-shape FlashAttention ABBA preflight passed\n'
  exit 0
fi

if [[ "$action" == run ]]; then
  [[ "$output_root" == /* ]] || fail 'output root must be absolute'
  [[ ! -e "$output_root" ]] || fail "refusing existing output root: $output_root"
  mkdir -- "$output_root"

  run_one() {
    local device=$1 slot=$2 role=$3 suffix=$4 stage output policy
    output="$output_root/gpu${device}-${slot}-${role}.json"
    if [[ "$role" == control ]]; then
      stage=$control_stage
      policy=0
      stage_args=(--stage "$control_stage")
    else
      stage=$candidate_stage
      policy=1
      stage_args=(--stage-manifest "$candidate_manifest")
    fi
    env -i \
      HOME=/home/steve \
      USER=steve \
      LOGNAME=steve \
      SHELL=/bin/bash \
      LANG=C.UTF-8 \
      PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
      PYTHONHASHSEED=0 \
      PYTHONDONTWRITEBYTECODE=1 \
      PYTHONPATH="$stage" \
      LD_LIBRARY_PATH="$stage/vllm_xpu_kernels:$venv_lib:$torch_lib" \
      ZE_AFFINITY_MASK="$device" \
      VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1 \
      VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY="$policy" \
      QWEN38_FA_CAMPAIGN_DRIVER="$driver" \
      QWEN38_FA_CAMPAIGN_DRIVER_SHA256="$driver_sha" \
      QWEN38_FA_LAB_REPO_HEAD="$repo_head" \
      "$python" "$operator" run \
        --role "$role" "${stage_args[@]}" --physical-gpu "$device" \
        --arm-id "gpu${device}-${suffix}" --campaign-slot "$slot" \
        --samples 40 --launches-per-sample 100 --stability-replays 32 \
        --output "$output"
  }

  # One process per arm, sequential A-B-B-A on each preregistered B70.
  for device in 2 3; do
    run_one "$device" 1 control a1
    run_one "$device" 2 candidate b1
    run_one "$device" 3 candidate b2
    run_one "$device" 4 control a2
  done
  printf 'PASS: eight fresh-process packets written; run compare as a separate action\n'
  exit 0
fi

[[ -d "$output_root" ]] || fail "missing output root: $output_root"
comparison="$output_root/comparison.json"
packets=()
for device in 2 3; do
  packets+=(
    "$output_root/gpu${device}-1-control.json"
    "$output_root/gpu${device}-2-candidate.json"
    "$output_root/gpu${device}-3-candidate.json"
    "$output_root/gpu${device}-4-control.json"
  )
done
for packet in "${packets[@]}"; do
  [[ -f "$packet" ]] || fail "missing run packet: $packet"
  jq -e \
    --arg operator_sha "$operator_sha" \
    --arg driver_sha "$driver_sha" \
    --arg repo_head "$repo_head" \
    '.runtime_identity.script_sha256 == $operator_sha and
     .runtime_identity.campaign_driver_sha256 == $driver_sha and
     .runtime_identity.lab_repo_head == $repo_head' \
    "$packet" >/dev/null || \
    fail "run packet does not match the current frozen harness/commit: $packet"
done
exec "$python" "$operator" compare --bootstrap-iterations 10000 \
  --output "$comparison" "${packets[@]}"
