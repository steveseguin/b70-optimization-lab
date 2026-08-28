#!/usr/bin/env bash
set -Eeuo pipefail

resource_dir=/var/tmp/q38-piecewise-graph-a4-resource
state=/tmp/q38-mtp0-current-piecewise-graph-a4
swapfile=/var/tmp/q38-piecewise-graph-a4-64g.swap
expected_swap_kib=67108860
root_floor_bytes=42949672960
mem_floor_kib=12582912
combined_mem_kib=16777216
combined_swap_free_kib=8388608
log="${resource_dir}/resource-watchdog.tsv"
resource_failure="${resource_dir}/resource.failed"
state_failure="${state}.failed"
stop_file="${resource_dir}/watchdog.stop"
heartbeat="${resource_dir}/watchdog.heartbeat-epoch"
psi_full_streak=0

write_atomic() {
  local path=$1 value=$2 tmp="${1}.tmp.$$"
  printf '%s\n' "$value" >"$tmp"
  mv "$tmp" "$path"
}

fail() {
  local reason=$1
  write_atomic "$resource_failure" "$reason"
  write_atomic "$state_failure" "FAIL graph attempt-4 resource watchdog: ${reason}"
  exit 1
}

[[ $# == 1 && "$1" =~ ^[1-9][0-9]*$ ]] || {
  printf 'FAIL: watchdog requires one owning supervisor PID\n' >&2
  exit 2
}
owner_pid=$1
[[ -e "/proc/${owner_pid}" ]] || { printf 'FAIL: owning supervisor absent\n' >&2; exit 1; }
owner_command=$(tr '\0' ' ' <"/proc/${owner_pid}/cmdline")
[[ "$owner_command" == *'supervise-tp4-mtp0-current-piecewise-graph-a4-swap64.sh'* ]] || {
  printf 'FAIL: owning supervisor identity mismatch\n' >&2
  exit 1
}
[[ -d "$resource_dir" && ! -e "$log" && ! -e "$resource_failure" && ! -e "$stop_file" && ! -e "$heartbeat" ]] || {
  printf 'FAIL: fresh resource evidence paths required\n' >&2
  exit 1
}
journal_start=$(cat "${resource_dir}/journal-start-epoch.txt" 2>/dev/null || true)
[[ "$journal_start" =~ ^[1-9][0-9]*$ ]] || { printf 'FAIL: journal start absent\n' >&2; exit 1; }
printf 'epoch\tmem_available_kib\tswap_total_kib\tswap_free_kib\tswap_used_kib\ttemp_swap_size_kib\ttemp_swap_used_kib\troot_available_bytes\tpswpin\tpswpout\tpsi_some_avg10\tpsi_full_avg10\tpsi_full_ge5_streak\n' >"$log"

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
  if awk -v value="$psi_full" 'BEGIN {exit !(value >= 5.0)}'; then
    psi_full_streak=$((psi_full_streak + 1))
  else
    psi_full_streak=0
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$epoch" "$mem_available" "$swap_total" "$swap_free" "$((swap_total - swap_free))" \
    "$temp_size" "$temp_used" "$root_available" "$pswpin" "$pswpout" "$psi_some" "$psi_full" "$psi_full_streak" >>"$log"
  write_atomic "$heartbeat" "$epoch"
  (( mem_available >= mem_floor_kib )) || fail "MemAvailable below 12 GiB: ${mem_available} KiB"
  (( mem_available >= combined_mem_kib || swap_free >= combined_swap_free_kib )) || \
    fail "combined pressure gate: MemAvailable=${mem_available} KiB and SwapFree=${swap_free} KiB"
  (( psi_full_streak < 30 )) || fail "memory PSI full avg10 >=5.0 for ${psi_full_streak} consecutive samples"
  (( root_available >= root_floor_bytes )) || fail "root available below 40 GiB: ${root_available} bytes"
  set +e
  journalctl -k --since "@${journal_start}" --no-pager >"${resource_dir}/watchdog-journal-current.log.tmp.$$" \
    2>"${resource_dir}/watchdog-journal-current.err.tmp.$$"
  journal_rc=$?
  set -e
  (( journal_rc == 0 )) || fail "kernel journal read failed: rc=${journal_rc}"
  mv "${resource_dir}/watchdog-journal-current.log.tmp.$$" "${resource_dir}/watchdog-journal-current.log"
  mv "${resource_dir}/watchdog-journal-current.err.tmp.$$" "${resource_dir}/watchdog-journal-current.err"
  ! grep -Eqi 'invoked oom-killer|Out of memory: Killed process|oom-kill:|RxErr' \
    "${resource_dir}/watchdog-journal-current.log" || fail 'new OOM or RxErr event in attempt-4 window'
  sleep 1
done

write_atomic "${resource_dir}/watchdog.rc" 0
