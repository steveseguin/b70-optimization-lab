#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
gate="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/benchmark-tp4-count2560-cpu-affinity.py"
postflight="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/verify-q38-four-b70-postflight.py"
venv=/home/steve/.venvs/vllm-xpu
python="${venv}/bin/python"
python_real=/home/steve/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12
torchrun="${venv}/bin/torchrun"
cmplr=/opt/intel/oneapi/compiler/2025.3
libccl="${venv}/lib/libccl.so.1"
libsycl="${venv}/lib/libsycl.so.8"
libfabric="${venv}/lib/libfabric.so.1"
ccl_kernels="${venv}/lib/ccl/kernels"
output=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-tp4-count2560-cpu-affinity-a1
runtime_state_dir="/run/user/$(id -u)"
full_load_lock="${runtime_state_dir}/q38-flash-next-full-load.boot-id.lock"
component_state_lock="${runtime_state_dir}/q38-flash-next-component-chain.state.lock"

expected_gate=a37f6d5c935ffbcc401fcc9197d49d8283fadba97e02037052d398779c7097c4
expected_postflight=cb42de925a4361f69a8922dacfda41cd02b6520f70df81011db2dd6a2c9b8753
expected_python=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
expected_torchrun=0d8056324b7819d01abb5e07e62286c56cbafec423edde8cf9ab2ae2a719912c
expected_libccl=ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3
expected_libsycl=0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f
expected_libfabric=d849d56fd3f8f2581b4b0c17c1564f8145911a313c2c011d694aaf21e5e86b27
expected_kernels=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

postflight_failure=
record_postflight_failure() {
  local message=$*
  postflight_failure+="${postflight_failure:+; }${message}"
  printf 'POSTFLIGHT_FAIL: %s\n' "$message" >&2
}

hash_regular() {
  local path=$1 expected=$2 label=$3
  [[ -f "$path" && ! -L "$path" ]] || fail "$label is not a regular non-symlink: $path"
  [[ "$(sha256sum "$path" | cut -d' ' -f1)" == "$expected" ]] || fail "$label hash drifted"
}

hash_python() {
  [[ -L "$python" && -f "$python" ]] || fail "python symlink is absent"
  [[ "$(readlink -f "$python")" == "$python_real" ]] || fail "python target drifted"
  [[ "$(sha256sum "$python" | cut -d' ' -f1)" == "$expected_python" ]] || fail "python hash drifted"
}

component_pids() {
  {
    pgrep -f -- "$gate" || true
    pgrep -f -- "$torchrun" || true
  } | awk -v self="$$" '$1 != self' | LC_ALL=C sort -un
}

cleanup_log=/dev/null
finalizer_armed=0
finalizer_ran=0
cleanup_components() {
  local -a pids=()
  mapfile -t pids < <(component_pids)
  ((${#pids[@]})) || return 0
  printf 'terminating exact component processes: %s\n' "${pids[*]}" >>"$cleanup_log"
  kill -TERM "${pids[@]}" 2>/dev/null || true
  for _ in {1..20}; do
    mapfile -t pids < <(component_pids)
    ((${#pids[@]})) || return 0
    sleep 0.1
  done
  printf 'force-stopping exact component processes: %s\n' "${pids[*]}" >>"$cleanup_log"
  kill -KILL "${pids[@]}" 2>/dev/null || true
}

finalize_on_exit() {
  local incoming_rc=$?
  local final_rc=$incoming_rc
  local memory_available swap_free
  local -a bdfs_after=()

  [[ "$finalizer_armed" == 1 ]] || return "$incoming_rc"
  [[ "$finalizer_ran" == 0 ]] || return "$incoming_rc"
  finalizer_ran=1
  trap - EXIT
  trap '' INT TERM
  set +Ee

  cleanup_components
  if [[ -n "$(component_pids)" ]]; then
    record_postflight_failure "final cleanup left an exact component process"
  fi

  if timeout 30s xpu-smi discovery -j >"$output/discovery-after.json"; then
    if jq -e '.device_list | type == "array"' "$output/discovery-after.json" >/dev/null 2>&1; then
      mapfile -t bdfs_after < <(jq -r '.device_list[].pci_bdf_address' "$output/discovery-after.json")
      [[ "${bdfs_after[*]}" == "0000:23:00.0 0000:27:00.0 0000:43:00.0 0000:47:00.0" ]] || \
        record_postflight_failure "postflight B70 order/topology drifted"
    else
      record_postflight_failure "postflight B70 discovery JSON is malformed"
    fi
  else
    record_postflight_failure "bounded postflight B70 discovery failed"
  fi

  if ! timeout --signal=TERM --kill-after=10s 90s env -i \
    HOME=/home/steve \
    PATH="${cmplr}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LD_LIBRARY_PATH="$loader" \
    OCL_ICD_FILENAMES="${cmplr}/lib/libintelocl.so" \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
    ZE_AFFINITY_MASK=0,1,2,3 \
    "$python" "$postflight" --output "$output/four-b70-postflight.json" \
    >"$output/four-b70-postflight.log" 2>&1; then
    record_postflight_failure "bounded four-B70 postflight failed"
  fi

  if awk '/MemAvailable|SwapFree/ {print}' /proc/meminfo >"$output/memory-after.txt"; then
    memory_available=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
    swap_free=$(awk '/SwapFree/ {print $2}' /proc/meminfo)
    [[ "$memory_available" =~ ^[0-9]+$ && "$memory_available" -ge 110000000 ]] || \
      record_postflight_failure "host memory did not recover after component"
    [[ "$swap_free" =~ ^[0-9]+$ && "$swap_free" -ge 8000000 ]] || \
      record_postflight_failure "free swap did not recover after component"
  else
    record_postflight_failure "could not capture host memory/swap postflight"
  fi

  if timeout 15s journalctl -b -k --after-cursor "$journal_cursor" --no-pager >"$output/journal-window.txt"; then
    rg -i '(xe|i915|drm).*(reset|fault|timed out|timeout|wedg|hang|error)|guc.*(reset|fault|timed out|timeout|wedg|hang|error)|device.*(lost|reset)|cat[_ ]error|page fault|gpu hang' \
      "$output/journal-window.txt" >"$output/journal-fault-matches.txt" || true
    [[ ! -s "$output/journal-fault-matches.txt" ]] || \
      record_postflight_failure "postflight kernel-journal fault signature found"
  else
    : >"$output/journal-fault-matches.txt"
    record_postflight_failure "could not capture the bounded kernel-journal window"
  fi

  printf 'incoming_rc=%s\npostflight=%s\n' "$incoming_rc" "${postflight_failure:-passed}" \
    >"$output/finalizer-status.txt" || record_postflight_failure "could not write finalizer status"
  if ! (cd "$output" && find . -type f ! -name evidence.sha256 -printf '%P\n' | LC_ALL=C sort | xargs -r sha256sum) \
    >"$output/evidence.sha256"; then
    record_postflight_failure "could not write the evidence manifest"
  elif ! (cd "$output" && sha256sum -c evidence.sha256) >/dev/null; then
    record_postflight_failure "evidence manifest verification failed"
  fi

  if [[ -n "$postflight_failure" && "$final_rc" == 0 ]]; then
    final_rc=1
  fi
  if [[ "$final_rc" == 0 ]]; then
    printf 'COMPLETE: %s\n' "$output/comparison.json"
  else
    printf 'FAIL: incoming_rc=%s; postflight=%s\n' \
      "$incoming_rc" "${postflight_failure:-passed}" >&2
  fi
  exit "$final_rc"
}
trap finalize_on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ $# == 0 ]] || fail "this frozen runner takes no arguments"
[[ "${Q38_RUN_COUNT2560_CPU_AFFINITY_A1:-}" == I_UNDERSTAND_THIS_USES_ALL_FOUR_GPUS ]] || \
  fail "set Q38_RUN_COUNT2560_CPU_AFFINITY_A1=I_UNDERSTAND_THIS_USES_ALL_FOUR_GPUS"
boot=$(tr -d '\n' </proc/sys/kernel/random/boot_id)
[[ ! -e "$output" ]] || fail "refusing to overwrite $output"
hash_regular "$gate" "$expected_gate" gate
hash_regular "$postflight" "$expected_postflight" postflight
hash_python
hash_regular "$torchrun" "$expected_torchrun" torchrun
hash_regular "$libccl" "$expected_libccl" libccl
hash_regular "$libsycl" "$expected_libsycl" libsycl
hash_regular "$libfabric" "$expected_libfabric" libfabric
hash_regular "$ccl_kernels/kernels.spv" "$expected_kernels" oneCCL-kernels
[[ "$(cat /sys/devices/system/cpu/online)" == 0-31 ]] || fail "CPU online set drifted"
[[ "$(cat /sys/devices/system/cpu/cpu0/cache/index3/shared_cpu_list)" == 0-7,16-23 ]] || fail "first L3 set drifted"
[[ "$(cat /sys/devices/system/cpu/cpu8/cache/index3/shared_cpu_list)" == 8-15,24-31 ]] || fail "second L3 set drifted"
"$python" - <<'PY'
import os
if sorted(os.sched_getaffinity(0)) != list(range(32)):
    raise SystemExit("runner CPU affinity is not 0-31")
PY
read -r source fstype target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)
[[ "$source" == /dev/sda2 && "$fstype" == fuseblk && "$target" == /mnt/usb-models ]] || fail "evidence drive is not authenticated"

# Serialize this independent component against model work and every B70. The
# lifecycle and component-state locks remain serialization locks, not same-boot
# experiment-count or predecessor-state admission gates.
exec 7>/tmp/b70-benchmark.lock
flock -n 7 || fail "the host benchmark lock is held"
exec 8>/tmp/b70-gpu0.lock
flock -n 8 || fail "the GPU0 benchmark lock is held"
exec 11>/tmp/b70-gpu1.lock
flock -n 11 || fail "the GPU1 benchmark lock is held"
exec 12>/tmp/b70-gpu2.lock
flock -n 12 || fail "the GPU2 benchmark lock is held"
exec 13>/tmp/b70-gpu3.lock
flock -n 13 || fail "the GPU3 benchmark lock is held"
exec 9>"$full_load_lock"
flock -n 9 || fail "the Flash-Next full-load lifecycle lock is held"
exec 10>"$component_state_lock"
flock -n 10 || fail "the Flash-Next component-chain lock is held"

journal_cursor=$(timeout 15s journalctl -b -k -n 0 --show-cursor --no-pager | sed -n 's/^-- cursor: //p' | tail -1)
[[ -n "$journal_cursor" ]] || fail "could not capture the pre-device kernel-journal cursor"
pgrep -af '(^|/)(vllm|python)( |.* )serve ' >/dev/null && fail "a model server is active"
memory_before=$(awk '/MemAvailable|SwapFree/ {print}' /proc/meminfo)
[[ "$(awk '/MemAvailable/ {print $2}' <<<"$memory_before")" -ge 110000000 ]] || fail "host memory is below the component floor"
[[ "$(awk '/SwapFree/ {print $2}' <<<"$memory_before")" -ge 8000000 ]] || fail "free swap is below the component floor"

mkdir -p "$output"
cleanup_log="$output/cleanup.log"
: >"$cleanup_log"
printf '%s\n' "$boot" >"$output/boot-id.txt"
printf '%s\n' "$journal_cursor" >"$output/journal-cursor-before.txt"
printf '%s\n' 'control-1 pinned-1 pinned-2 control-2' >"$output/launch-order.txt"
printf '%s\n' "$memory_before" >"$output/memory-before.txt"

loader="${venv}/lib:${venv}/lib/python3.12/site-packages/torch/lib:${cmplr}/lib:${cmplr}/opt/compiler/lib"
finalizer_armed=1
timeout 30s xpu-smi discovery -j >"$output/discovery-before.json" || fail "bounded preflight B70 discovery failed"
mapfile -t bdfs < <(jq -r '.device_list[].pci_bdf_address' "$output/discovery-before.json")
[[ "${bdfs[*]}" == "0000:23:00.0 0000:27:00.0 0000:43:00.0 0000:47:00.0" ]] || fail "B70 order/topology drifted"
timeout --signal=TERM --kill-after=10s 90s env -i \
  HOME=/home/steve \
  PATH="${cmplr}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  LD_LIBRARY_PATH="$loader" \
  OCL_ICD_FILENAMES="${cmplr}/lib/libintelocl.so" \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
  ZE_AFFINITY_MASK=0,1,2,3 \
  "$python" "$postflight" --output "$output/four-b70-preflight.json" \
  >"$output/four-b70-preflight.log" 2>&1 || fail "bounded four-B70 preflight failed"
arms=(control-1 pinned-1 pinned-2 control-2)
for arm in "${arms[@]}"; do
  mode=${arm%%-*}
  worker_affinity=31,30,29,28
  [[ "$mode" == pinned ]] && worker_affinity=19,23,27,31
  arm_dir="${output}/${arm}"
  mkdir "$arm_dir"
  set +e
  timeout --signal=TERM --kill-after=20s 300s env -i \
    HOME=/home/steve \
    PATH="${cmplr}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LIBRARY_PATH="${cmplr}/lib:${cmplr}/opt/compiler/lib" \
    LD_LIBRARY_PATH="$loader" \
    OCL_ICD_FILENAMES="${cmplr}/lib/libintelocl.so" \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 ZE_AFFINITY_MASK=0,1,2,3 \
    CCL_ATL_TRANSPORT=ofi FI_PROVIDER=tcp FI_TCP_IFACE=lo CCL_KVS_IFACE=lo \
    CCL_ZE_IPC_EXCHANGE=pidfd CCL_SEND=direct CCL_RECV=direct \
    CCL_WORKER_AFFINITY="$worker_affinity" \
    CCL_TOPO_P2P_ACCESS=1 CCL_KERNEL_PATH="$ccl_kernels" \
    CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
    CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
    CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
    CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096 \
    "$torchrun" --standalone --nproc-per-node=4 \
      "$gate" --mode "$mode" --output-dir "$arm_dir" \
      >"$arm_dir/torchrun.log" 2>&1
  code=$?
  set -e
  printf '%s\n' "$code" >"$arm_dir/exit-code.txt"
  if [[ -n "$(component_pids)" ]]; then
    cleanup_components
    [[ -z "$(component_pids)" ]] || fail "$arm cleanup left a process"
    fail "$arm left a process; it was terminated"
  fi
  [[ "$code" == 0 ]] || fail "$arm failed with exit $code"
  [[ -s "$arm_dir/summary.json" ]] || fail "$arm lacks a complete summary"
done

set +e
"$python" - "$output" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
names = ("control-1", "pinned-1", "pinned-2", "control-2")
arms = {name: json.loads((root / name / "summary.json").read_text()) for name in names}
if [arms[name]["mode"] for name in names] != ["control", "pinned", "pinned", "control"]:
    raise SystemExit("arm modes drifted")
hashes = {arms[name]["output_sha256"] for name in names}
if len(hashes) != 1:
    raise SystemExit(f"arm output hashes differ: {hashes}")
pairs = (("control-1", "pinned-1"), ("control-2", "pinned-2"))
pair_rows = []
for control_name, pinned_name in pairs:
    control = arms[control_name]["slowest_rank_latency"]
    pinned = arms[pinned_name]["slowest_rank_latency"]
    median_fraction = (control["median_ms"] - pinned["median_ms"]) / control["median_ms"]
    p90_fraction = (control["p90_ms"] - pinned["p90_ms"]) / control["p90_ms"]
    pair_rows.append({
        "control": control_name,
        "pinned": pinned_name,
        "control_median_ms": control["median_ms"],
        "pinned_median_ms": pinned["median_ms"],
        "median_saving_fraction": median_fraction,
        "p90_saving_fraction": p90_fraction,
        "passed": median_fraction >= 0.05 and p90_fraction >= 0.0,
    })
passed = all(row["passed"] for row in pair_rows)
result = {
    "schema_version": 1,
    "status": "passed" if passed else "closed",
    "classification": "component_pass_endpoint_candidate" if passed else "component_closed_no_endpoint",
    "scope": "ordinary accepted XCCL; CPU/L3 affinity only; not model throughput",
    "required_median_saving_fraction_each_pair": 0.05,
    "required_nonnegative_p90_saving_each_pair": True,
    "output_sha256": next(iter(hashes)),
    "pairs": pair_rows,
    "arm_summary_sha256": {
        name: hashlib.sha256((root / name / "summary.json").read_bytes()).hexdigest()
        for name in names
    },
}
(root / "comparison.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, sort_keys=True))
PY
comparison_code=$?
set -e
[[ "$comparison_code" == 0 ]] || fail "comparison failed with exit $comparison_code"
exit 0
