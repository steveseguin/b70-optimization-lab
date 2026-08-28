#!/usr/bin/env bash
set -Eeuo pipefail

resource_dir=/var/tmp/q38-piecewise-graph-a7-resource
state=/tmp/q38-mtp0-current-piecewise-graph-a7
swapfile=/var/tmp/q38-piecewise-graph-a7-64g.swap
expected_swap_kib=67108860
root_floor_bytes=42949672960
mem_floor_kib=12582912
phase_mem_floor_kib=31457280
phase_drop_floor_kib=41943040
phase_drop_limit_kib=8388608
combined_mem_kib=16777216
combined_swap_free_kib=8388608
classifier=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/classify-q38-piecewise-graph-a5-kernel-journal.py
expected_classifier=440d7d0636bef8b5baf9bd5603ced988e22fe64c7df912ed15e55561aea8ea16
log="${resource_dir}/resource-watchdog.tsv"
resource_failure="${resource_dir}/resource.failed"
state_failure="${state}.failed"
stop_file="${resource_dir}/watchdog.stop"
heartbeat="${resource_dir}/watchdog.heartbeat-epoch"
server_log=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt7/server.log
psi_full_streak=0
phase_active=0
previous_mem_available=""

write_atomic() {
  local path=$1 value=$2 tmp="${1}.tmp.$$"
  printf '%s\n' "$value" >"$tmp"
  mv "$tmp" "$path"
}

fail() {
  local reason=$1
  write_atomic "$resource_failure" "$reason"
  write_atomic "$state_failure" "FAIL graph attempt-7 resource watchdog: ${reason}"
  exit 1
}

audit_kernel_journal() {
  local journal=$1 allowed_tmp="${resource_dir}/root-nvme-corrected-events.log.tmp.$$"
  "$classifier" "$journal" "$allowed_tmp" || \
    fail 'kernel journal event-block policy refused the attempt-7 window'
  mv "$allowed_tmp" "${resource_dir}/root-nvme-corrected-events.log"
}

[[ $# == 1 && "$1" =~ ^[1-9][0-9]*$ ]] || {
  printf 'FAIL: watchdog requires one owning supervisor PID\n' >&2
  exit 2
}
printf '%s  %s\n' "$expected_classifier" "$classifier" | sha256sum -c - >/dev/null || {
  printf 'FAIL: journal classifier hash changed\n' >&2
  exit 1
}
owner_pid=$1
[[ -e "/proc/${owner_pid}" ]] || { printf 'FAIL: owning supervisor absent\n' >&2; exit 1; }
owner_command=$(tr '\0' ' ' <"/proc/${owner_pid}/cmdline")
[[ "$owner_command" == *'supervise-tp4-mtp0-current-piecewise-graph-a7-swap64.sh'* ]] || {
  printf 'FAIL: owning supervisor identity mismatch\n' >&2
  exit 1
}
[[ -d "$resource_dir" && ! -e "$log" && ! -e "$resource_failure" && ! -e "$stop_file" && ! -e "$heartbeat" ]] || {
  printf 'FAIL: fresh resource evidence paths required\n' >&2
  exit 1
}
journal_start=$(cat "${resource_dir}/journal-start-epoch.txt" 2>/dev/null || true)
[[ "$journal_start" =~ ^[1-9][0-9]*$ ]] || { printf 'FAIL: journal start absent\n' >&2; exit 1; }
printf 'epoch\tmem_available_kib\tswap_total_kib\tswap_free_kib\tswap_used_kib\ttemp_swap_size_kib\ttemp_swap_used_kib\troot_available_bytes\tpswpin\tpswpout\tpsi_some_avg10\tpsi_full_avg10\tpsi_full_ge5_streak\tcompile_pressure_phase\tloaded_rank_count\tcompile_marker\tmem_drop_kib\n' >"$log"

while kill -0 "$owner_pid" 2>/dev/null; do
  [[ ! -e "$stop_file" ]] || break
  epoch=$(date +%s)
  mem_available=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
  swap_total=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
  swap_free=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
  temp_row=$(awk -v path="$swapfile" '$1 == path {print $3 " " $4}' /proc/swaps)
  root_available=$(df -PB1 /var/tmp | awk 'NR==2 {print $4}')
  pswpin=$(awk '$1 == "pswpin" {print $2}' /proc/vmstat)
  pswpout=$(awk '$1 == "pswpout" {print $2}' /proc/vmstat)
  psi_some=$(awk '$1 == "some" {sub(/^avg10=/,"",$2); print $2}' /proc/pressure/memory)
  psi_full=$(awk '$1 == "full" {sub(/^avg10=/,"",$2); print $2}' /proc/pressure/memory)
  [[ "$mem_available" =~ ^[0-9]+$ && "$swap_total" =~ ^[0-9]+$ && \
     "$swap_free" =~ ^[0-9]+$ && "$root_available" =~ ^[0-9]+$ && \
     "$temp_row" =~ ^[0-9]+\ [0-9]+$ && "$pswpin" =~ ^[0-9]+$ && \
     "$pswpout" =~ ^[0-9]+$ && "$psi_some" =~ ^[0-9]+([.][0-9]+)?$ && \
     "$psi_full" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail 'resource sample unavailable'
  read -r temp_size temp_used <<<"$temp_row"
  (( temp_size == expected_swap_kib )) || fail "temporary swap size changed: ${temp_size} KiB"
  loaded_rank_count=0
  compile_marker=0
  if [[ -f "$server_log" ]]; then
    loaded_rank_count=$({ grep -aoE 'Worker_TP[0-3]_EP[0-3].*Model loading took' "$server_log" 2>/dev/null || true; } | \
      sed -E 's/.*Worker_TP([0-3])_EP([0-3]).*/\1:\2/' | sort -u | wc -l)
    grep -aEq 'Dynamo bytecode transform time:|Cache the graph of compile range|Capturing CUDA graphs \(mixed prefill-decode, PIECEWISE\)' "$server_log" && compile_marker=1 || true
  fi
  if (( phase_active == 0 && (loaded_rank_count == 4 || compile_marker == 1) )); then
    phase_active=1
    write_atomic "${resource_dir}/compile-pressure-phase.txt" \
      "epoch=${epoch} loaded_rank_count=${loaded_rank_count} compile_marker=${compile_marker}"
  fi
  mem_drop_kib=0
  if [[ "$previous_mem_available" =~ ^[0-9]+$ && previous_mem_available -gt mem_available ]]; then
    mem_drop_kib=$((previous_mem_available - mem_available))
  fi
  if awk -v value="$psi_full" 'BEGIN {exit !(value >= 5.0)}'; then
    psi_full_streak=$((psi_full_streak + 1))
  else
    psi_full_streak=0
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$epoch" "$mem_available" "$swap_total" "$swap_free" "$((swap_total - swap_free))" \
    "$temp_size" "$temp_used" "$root_available" "$pswpin" "$pswpout" "$psi_some" "$psi_full" "$psi_full_streak" \
    "$phase_active" "$loaded_rank_count" "$compile_marker" "$mem_drop_kib" >>"$log"
  write_atomic "$heartbeat" "$epoch"
  (( mem_available >= mem_floor_kib )) || fail "MemAvailable below 12 GiB: ${mem_available} KiB"
  if (( phase_active == 1 )); then
    (( mem_available >= phase_mem_floor_kib )) || \
      fail "compile-pressure phase MemAvailable below 30 GiB: ${mem_available} KiB"
    (( mem_available >= phase_drop_floor_kib || mem_drop_kib < phase_drop_limit_kib )) || \
      fail "compile-pressure phase one-sample MemAvailable drop >=8 GiB below 40 GiB: drop=${mem_drop_kib} current=${mem_available} KiB"
  fi
  (( mem_available >= combined_mem_kib || swap_free >= combined_swap_free_kib )) || \
    fail "combined pressure gate: MemAvailable=${mem_available} KiB and SwapFree=${swap_free} KiB"
  (( psi_full_streak < 30 )) || fail "memory PSI full avg10 >=5.0 for ${psi_full_streak} consecutive samples"
  (( root_available >= root_floor_bytes )) || fail "root available below 40 GiB: ${root_available} bytes"
  set +e
  timeout --signal=TERM --kill-after=5s 20s journalctl -k --since "@${journal_start}" --no-pager \
    >"${resource_dir}/watchdog-journal-current.log.tmp.$$" \
    2>"${resource_dir}/watchdog-journal-current.err.tmp.$$"
  journal_rc=$?
  set -e
  (( journal_rc == 0 )) || fail "kernel journal read failed: rc=${journal_rc}"
  mv "${resource_dir}/watchdog-journal-current.log.tmp.$$" "${resource_dir}/watchdog-journal-current.log"
  mv "${resource_dir}/watchdog-journal-current.err.tmp.$$" "${resource_dir}/watchdog-journal-current.err"
  if grep -Eqi '\[TTM\].*Buffer eviction failed|page allocation failure|invoked oom-killer|oom-kill:|Out of memory: Killed process|Memory cgroup out of memory' \
    "${resource_dir}/watchdog-journal-current.log"; then
    fail 'immediate memory-allocation/eviction/OOM signature in kernel journal'
  fi
  audit_kernel_journal "${resource_dir}/watchdog-journal-current.log"
  previous_mem_available=$mem_available
  sleep 1
done

write_atomic "${resource_dir}/watchdog.rc" 0
