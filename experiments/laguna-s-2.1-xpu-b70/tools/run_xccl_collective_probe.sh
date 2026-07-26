#!/usr/bin/env bash
# Launch the 4-rank XCCL probe under a named CCL configuration.
# usage: xccl_probe.sh LABEL [EXTRA_ENV=VAL ...]
set -uo pipefail

label="${1:?usage: xccl_probe.sh LABEL [ENV=VAL ...]}"
shift

readonly scratch=${XCCL_PROBE_SCRATCH:?set XCCL_PROBE_SCRATCH to a writable scratch dir}
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly out="$scratch/probe-$label"
rm -rf "$out"; mkdir -p "$out"

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
    "$python" "$scratch/xccl_probe.py" \
    >"$out/rank$rank.log" 2>&1 &
  pids+=($!)
done

fail=0
for p in "${pids[@]}"; do wait "$p" || fail=1; done

echo "=== $label: exit_nonzero=$fail ==="
for rank in 0 1 2 3; do
  printf 'rank%s: %s\n' "$rank" "$(grep -c 'all_reduce-done' "$out/rank$rank.log" 2>/dev/null)"
done
echo "--- furthest stage reached (rank0) ---"
grep -E '^\[rank' "$out/rank0.log" 2>/dev/null | tail -3
echo "--- first error (any rank) ---"
grep -hEm1 'Error|error|Traceback|Abort|assert' "$out"/rank*.log 2>/dev/null | head -3
exit "$fail"
