#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8.sh"
expected_base=bfb70ca1cdb74f5c7ec4bf462755c250cebbf71a828fd42d18b09c36e7c13bb0
expected_wrapper=2d803d131608c66f549372de34df898ee3acda5efb224511b7d8bac10ae3c35a
expected_client=6ee63ac76a541de3b0eb088994b6c936e387a59751b84e1ccbafa06557915360
postflight="${script_dir}/verify-q38-four-b70-postflight.py"
expected_postflight=cb42de925a4361f69a8922dacfda41cd02b6520f70df81011db2dd6a2c9b8753
python=/home/steve/.venvs/vllm-xpu/bin/python
current_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9
expected_source=20404a46bd355f3a16254d2ea627a7cccad87ccb94e5a2f40f4eb1e4be8fa675
lifecycle_evidence=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt32-lifecycle
lifecycle_started=0
lifecycle_finished=0
journal_cursor=""

derive() {
  Q38_A29_SOURCE_ONLY=1 "$base" | awk \
    -v wrapper_hash="$expected_wrapper" \
    -v client_hash="$expected_client" \
    -v current_vllm="$current_vllm" '
{
  gsub(/ple-only-a29-moe-m1-warps8/, "ple-only-a32-moe-m1-current")
  gsub(/q38-mtp0-ple-only-a29/, "q38-mtp0-ple-only-a32")
  gsub(/q38-ple4k-a29/, "q38-ple4k-a32")
  gsub(/attempt29/, "attempt32")
  gsub(/19701/, "19704")
  gsub(/A29/, "A32")
  gsub(/d14396e27247c1b251da0ce24a0942772c4b002f/, current_vllm)
  if ($0 == "expected_wrapper=6a624362e1ae1d4c4522fbc6cd88c6ac9e7da0da7998390c28333927c3aec5b0") {
    print "expected_wrapper=" wrapper_hash
    next
  }
  if ($0 == "expected_client=28e89555634fe22a06cf87d8bc15fbb69fe6230981ddaef34d9a7fe1476b6981") {
    print "expected_client=" client_hash
    next
  }
  if ($0 == "  HOME=/home/steve USER=steve LOGNAME=steve LANG=C.UTF-8 \\") {
    print
    print "  Q38_A32_SUPERVISOR_PID=\"${Q38_A32_SUPERVISOR_PID}\" \\"
    print "  Q38_A32_SUPERVISOR_STARTTIME=\"${Q38_A32_SUPERVISOR_STARTTIME}\" \\"
    next
  }
  print
}
'
}

write_atomic() {
  local path=$1 value=$2 temporary
  temporary="${path}.tmp.$$"
  [[ ! -e "$temporary" ]] || { printf 'FAIL: refusing to reuse %s\n' "$temporary" >&2; return 1; }
  printf '%s\n' "$value" >"$temporary"
  mv "$temporary" "$path"
}

capture_host_state() {
  local label=$1
  cp /proc/meminfo "${lifecycle_evidence}/meminfo-${label}.txt"
  cp /proc/swaps "${lifecycle_evidence}/swaps-${label}.txt"
  df -B1 / /tmp /dev/shm /mnt/fast-ai /mnt/usb-models \
    >"${lifecycle_evidence}/filesystem-${label}.txt"
}

capture_topology() {
  local label=$1 device memory
  timeout 30s xpu-smi discovery -j >"${lifecycle_evidence}/xpu-discovery-${label}.json" \
    2>"${lifecycle_evidence}/xpu-discovery-${label}.err" || return 1
  jq -e '.device_list | map([
      .device_id, .device_name, .pci_bdf_address, .drm_device
    ]) == [
      [0, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:23:00.0", "/dev/dri/card3"],
      [1, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:27:00.0", "/dev/dri/card4"],
      [2, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:43:00.0", "/dev/dri/card0"],
      [3, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:47:00.0", "/dev/dri/card2"]
    ]' "${lifecycle_evidence}/xpu-discovery-${label}.json" >/dev/null || return 1
  for device in 0 1 2 3; do
    timeout 30s xpu-smi stats -d "$device" -j \
      >"${lifecycle_evidence}/xpu-stats-${device}-${label}.json" \
      2>"${lifecycle_evidence}/xpu-stats-${device}-${label}.err" || return 1
    memory=$(jq -er 'first(.device_level[] | select(.metrics_type == "XPUM_STATS_MEMORY_USED") | .value)' \
      "${lifecycle_evidence}/xpu-stats-${device}-${label}.json") || return 1
    awk -v value="$memory" 'BEGIN { exit !(value < 256) }' || return 1
  done
}

run_four_card_check() {
  local label=$1
  timeout --signal=TERM --kill-after=10s 90s env -i \
    HOME=/home/steve USER=steve LOGNAME=steve LANG=C.UTF-8 \
    PATH=/opt/intel/oneapi/compiler/2025.3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LD_LIBRARY_PATH=/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib \
    OCL_ICD_FILENAMES=/opt/intel/oneapi/compiler/2025.3/lib/libintelocl.so \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
    ZE_AFFINITY_MASK=0,1,2,3 \
    "$python" "$postflight" --output "${lifecycle_evidence}/four-b70-${label}.json" \
    >"${lifecycle_evidence}/four-b70-${label}.log" 2>&1 || return 1
  jq -e '.status == "passed" and .device_count == 4 and
    (.devices | length) == 4 and all(.devices[]; .free_fraction >= .90)' \
    "${lifecycle_evidence}/four-b70-${label}.json" >/dev/null
}

close_lifecycle() {
  local incoming_rc=$?
  local final_rc=$incoming_rc postflight_rc=0 lifecycle_status mem_available_kib swap_free_kib nvme_available_bytes
  trap - EXIT
  if (( lifecycle_started == 1 && lifecycle_finished == 0 )); then
    set +e
    capture_host_state after || postflight_rc=1
    capture_topology after || postflight_rc=1
    run_four_card_check postflight || postflight_rc=1
    timeout 15s journalctl -b -k --after-cursor "$journal_cursor" --no-pager \
      >"${lifecycle_evidence}/kernel-journal-window.txt" \
      2>"${lifecycle_evidence}/kernel-journal-window.err" || postflight_rc=1
    rg -i '(xe|i915|drm).*(reset|fault|timed out|timeout|wedg|hang|error)|guc.*(reset|fault|timed out|timeout|wedg|hang|error)|device.*(lost|reset)|cat[_ ]error|page fault|gpu hang' \
      "${lifecycle_evidence}/kernel-journal-window.txt" \
      >"${lifecycle_evidence}/kernel-journal-fault-matches.txt" || true
    [[ ! -s "${lifecycle_evidence}/kernel-journal-fault-matches.txt" ]] || postflight_rc=1
    mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    swap_free_kib=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
    nvme_available_bytes=$(df -B1 --output=avail /mnt/fast-ai | tail -1 | tr -d ' ')
    (( mem_available_kib >= 100 * 1024 * 1024 )) || postflight_rc=1
    (( swap_free_kib >= 6 * 1024 * 1024 )) || postflight_rc=1
    (( nvme_available_bytes >= 220000000000 )) || postflight_rc=1
    (( postflight_rc == 0 )) || final_rc=70
    if (( postflight_rc != 0 )); then
      lifecycle_status=postflight_failed
    elif (( incoming_rc != 0 )); then
      lifecycle_status=inner_supervisor_failed
    else
      lifecycle_status=passed
    fi
    jq -n \
      --arg status "$lifecycle_status" \
      --argjson inner_rc "$incoming_rc" --argjson final_rc "$final_rc" \
      --argjson mem_available_kib "$mem_available_kib" \
      --argjson swap_free_kib "$swap_free_kib" \
      --argjson nvme_available_bytes "$nvme_available_bytes" \
      '{schema_version: 1, status: $status, inner_supervisor_rc: $inner_rc,
        final_rc: $final_rc, recovery_floors: {
          mem_available_kib: $mem_available_kib,
          swap_free_kib: $swap_free_kib,
          nvme_available_bytes: $nvme_available_bytes}}' \
      >"${lifecycle_evidence}/lifecycle-summary.json"
    write_atomic "${lifecycle_evidence}/final.rc" "$final_rc" || final_rc=70
    (
      cd "$lifecycle_evidence" || exit 1
      find . -type f ! -name evidence.sha256 -printf '%P\n' | LC_ALL=C sort | \
        xargs -r sha256sum >evidence.sha256
      sha256sum -c evidence.sha256 >/dev/null
    ) || final_rc=70
    lifecycle_finished=1
  fi
  exit "$final_rc"
}
trap close_lifecycle EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

[[ $# == 0 ]] || { printf 'FAIL: A32 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: A32 base supervisor drifted\n' >&2
  exit 1
}
[[ "$(sha256sum "$postflight" | cut -d' ' -f1)" == "$expected_postflight" ]] || {
  printf 'FAIL: A32 four-card helper drifted\n' >&2
  exit 1
}
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A32 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A32_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi

[[ ! -e "$lifecycle_evidence" ]] || {
  printf 'FAIL: refusing to reuse %s\n' "$lifecycle_evidence" >&2
  exit 1
}
exec 7>/tmp/b70-benchmark.lock
flock -n 7 || { printf 'FAIL: host-wide benchmark lock is held\n' >&2; exit 1; }
for gpu in 0 1 2 3; do
  eval "exec $((8 + gpu))>/tmp/b70-gpu${gpu}.lock"
  flock -n "$((8 + gpu))" || { printf 'FAIL: GPU %s lock is held\n' "$gpu" >&2; exit 1; }
done

mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
swap_free_kib=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
nvme_available_bytes=$(df -B1 --output=avail /mnt/fast-ai | tail -1 | tr -d ' ')
(( mem_available_kib >= 120000000 )) || { printf 'FAIL: A32 requires MemAvailable >= 120000000 KiB\n' >&2; exit 1; }
(( swap_free_kib >= 8000000 )) || { printf 'FAIL: A32 requires SwapFree >= 8000000 KiB\n' >&2; exit 1; }
(( nvme_available_bytes >= 220000000000 )) || { printf 'FAIL: A32 requires >= 220000000000 free NVMe bytes\n' >&2; exit 1; }

mkdir -p "$lifecycle_evidence"
lifecycle_started=1
journal_cursor=$(timeout 15s journalctl -b -k -n 0 --show-cursor --no-pager | \
  sed -n 's/^-- cursor: //p' | tail -1)
[[ -n "$journal_cursor" ]] || { printf 'FAIL: could not capture A32 kernel-journal cursor\n' >&2; exit 1; }
printf '%s\n' "$journal_cursor" >"${lifecycle_evidence}/kernel-journal-cursor-before.txt"
tr -d '\n' </proc/sys/kernel/random/boot_id >"${lifecycle_evidence}/boot-id.txt"
printf '\n' >>"${lifecycle_evidence}/boot-id.txt"
capture_host_state before
capture_topology before || { printf 'FAIL: A32 four-card preflight topology is not exact and idle\n' >&2; exit 1; }
run_four_card_check preflight || { printf 'FAIL: A32 bounded four-card preflight failed\n' >&2; exit 1; }

export Q38_A32_SUPERVISOR_PID=$$
Q38_A32_SUPERVISOR_STARTTIME=$(awk '{ line=$0; sub(/^.*\) /, "", line); split(line, fields, " "); print fields[20] }' "/proc/$$/stat")
export Q38_A32_SUPERVISOR_STARTTIME
set +e
bash <(derive)
inner_rc=$?
set -e
exit "$inner_rc"
