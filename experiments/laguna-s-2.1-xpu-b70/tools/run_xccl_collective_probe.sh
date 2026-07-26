#!/usr/bin/env bash
# Launch the 4-rank XCCL probe under a named CCL configuration.
# usage: run_xccl_collective_probe.sh LABEL [EXTRA_ENV=VAL ...]
set -uo pipefail
umask 077

die() {
  printf 'xccl-probe: %s\n' "$*" >&2
  printf 'PROBE_RESULT=HARNESS_FAILURE\n' >&2
  exit 2
}

[[ $# -ge 1 ]] || die "usage: run_xccl_collective_probe.sh LABEL [ENV=VAL ...]"
label=$1
shift

[[ "$label" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$ ]] \
  || die "LABEL must contain only letters, digits, dot, underscore, or dash"
[[ -n ${XCCL_PROBE_SCRATCH:-} ]] \
  || die "set XCCL_PROBE_SCRATCH to a fresh writable scratch directory"
readonly scratch=$XCCL_PROBE_SCRATCH
[[ "$scratch" == /* ]] || die "XCCL_PROBE_SCRATCH must be an absolute path"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" \
  || die "cannot resolve the probe script directory"
readonly script_dir
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly probe_source="$script_dir/xccl_collective_probe.py"
readonly out="$scratch/probe-$label"

[[ -x "$python" ]] || die "Python interpreter is not executable: $python"
[[ -f "$probe_source" && -r "$probe_source" ]] \
  || die "probe source is not a readable regular file: $probe_source"

for assignment in "$@"; do
  [[ "$assignment" == *=* ]] \
    || die "extra arguments must be environment assignments: $assignment"
  key=${assignment%%=*}
  [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] \
    || die "invalid environment variable name: $key"
  case "$key" in
    PATH|LANG|LC_ALL|HOME|TMPDIR|PYTHONDONTWRITEBYTECODE|PYTHONNOUSERSITE|\
    LD_LIBRARY_PATH|MASTER_ADDR|MASTER_PORT|WORLD_SIZE|RANK|OMP_NUM_THREADS)
      die "environment override is reserved by the probe harness: $key"
      ;;
  esac
done

mkdir -p -- "$scratch" || die "cannot create scratch directory: $scratch"
mkdir -- "$out" \
  || die "probe output already exists; choose a fresh label or scratch: $out"
printf 'probe_artifacts=%s\n' "$out"
printf 'probe_source=%s\n' "$probe_source"

port=$(( 29500 + RANDOM % 2000 ))

base_env=(
  PATH=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
  LANG=C.UTF-8 LC_ALL=C.UTF-8
  HOME="$out"
  TMPDIR="$out"
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
  LD_LIBRARY_PATH=/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib
  MASTER_ADDR=127.0.0.1
  MASTER_PORT="$port"
  WORLD_SIZE=4
  OMP_NUM_THREADS=1
)

pids=()
for rank in 0 1 2 3; do
  /usr/bin/timeout --signal=TERM --kill-after=20s 150s \
    /usr/bin/env -i "${base_env[@]}" RANK="$rank" "$@" \
    "$python" "$probe_source" \
    >"$out/rank$rank.log" 2>&1 &
  pids+=("$!")
done

exit_codes=()
process_fail=0
for p in "${pids[@]}"; do
  if wait "$p"; then
    rc=0
  else
    rc=$?
    process_fail=1
  fi
  exit_codes+=("$rc")
done

stage_count() {
  local rank=$1
  local pattern=$2
  local log="$out/rank$rank.log"
  [[ -f "$log" ]] || {
    printf '0\n'
    return
  }
  grep -Ec \
    "^\[rank ${rank}\] ${pattern} t=[0-9]+\.[0-9]{2}$" \
    "$log" 2>/dev/null || true
}

imports=0
devices=0
process_groups=0
tensors=0
reduction_starts=0
reductions=0
verifications=0
teardowns=0

echo "=== $label ==="
for rank in 0 1 2 3; do
  import_ok=0
  device_ok=0
  process_group_ok=0
  tensor_ok=0
  reduction_start_ok=0
  reduction_ok=0
  verification_ok=0
  teardown_ok=0

  [[ $(stage_count "$rank" "import-done") == 1 ]] && import_ok=1
  [[ $(stage_count "$rank" "device-set .+") == 1 ]] && device_ok=1
  [[ $(stage_count "$rank" "pg-initialised") == 1 ]] && process_group_ok=1
  [[ $(stage_count "$rank" "tensor-allocated") == 1 ]] && tensor_ok=1
  [[ $(stage_count "$rank" "all_reduce-start") == 1 ]] && reduction_start_ok=1
  [[ $(stage_count "$rank" "all_reduce-done sum=10\.0") == 1 ]] \
    && reduction_ok=1
  [[ $(stage_count "$rank" "verify OK expected=10\.0") == 1 ]] \
    && verification_ok=1
  [[ $(stage_count "$rank" "teardown-done") == 1 ]] && teardown_ok=1

  ((imports += import_ok))
  ((devices += device_ok))
  ((process_groups += process_group_ok))
  ((tensors += tensor_ok))
  ((reduction_starts += reduction_start_ok))
  ((reductions += reduction_ok))
  ((verifications += verification_ok))
  ((teardowns += teardown_ok))

  furthest=not-started
  ((import_ok)) && furthest=import-done
  ((device_ok)) && furthest=device-set
  ((process_group_ok)) && furthest=pg-initialised
  ((tensor_ok)) && furthest=tensor-allocated
  ((reduction_start_ok)) && furthest=all_reduce-start
  ((reduction_ok)) && furthest=all_reduce-done
  ((verification_ok)) && furthest=verify-OK
  ((teardown_ok)) && furthest=teardown-done

  rank_result=FAIL
  if ((
    import_ok
    && device_ok
    && process_group_ok
    && tensor_ok
    && reduction_start_ok
    && reduction_ok
    && verification_ok
    && teardown_ok
    && exit_codes[rank] == 0
  )); then
    rank_result=PASS
  fi
  printf 'rank%s: %s exit=%s furthest=%s\n' \
    "$rank" "$rank_result" "${exit_codes[rank]}" "$furthest"
done

result=PASS
if ((imports != 4)); then
  result=HARNESS_OR_IMPORT_FAILURE
elif ((devices != 4)); then
  result=DEVICE_SETUP_FAILURE
elif ((process_groups != 4)); then
  result=PROCESS_GROUP_INIT_FAILURE
elif ((tensors != 4)); then
  result=TENSOR_SETUP_FAILURE
elif ((reduction_starts != 4)); then
  result=PRE_COLLECTIVE_FAILURE
elif ((reductions != 4)); then
  result=COLLECTIVE_STAGE_FAILURE
elif ((verifications != 4)); then
  result=VERIFICATION_FAILURE
elif ((teardowns != 4)); then
  result=TEARDOWN_FAILURE
elif ((process_fail)); then
  result=PROCESS_EXIT_FAILURE
fi

echo "--- first error (any rank) ---"
grep -hEm1 'Error|error|Traceback|Abort|assert' "$out"/rank*.log 2>/dev/null | head -3
printf 'PROBE_RESULT=%s clean_teardowns=%s/4 artifacts=%s\n' \
  "$result" "$teardowns" "$out"

[[ "$result" == PASS ]]
