#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_supervisor="${script_dir}/supervise-tp4-mtp0-current-piecewise-graph-a1.sh"
expected_source=414dd8ad9a1d07ae78b66512bdfdb1d453516a35c6528ecf0e6cc2b94bf7c3df
wrapper="${script_dir}/launch-tp4-mtp0-current-piecewise-graph-a5.sh"
expected_wrapper=19f08177b2d12bd25e9b2c21f96fb5ee81aec7b8bd6c8c8e37af00b289631487
client="${script_dir}/run-tp4-mtp0-current-piecewise-graph-a5-client.sh"
expected_client=8da39d3c001651c05ca1d534c8e80f7f326207a61ead89a3be1499e1c14203b9
watchdog="${script_dir}/watch-tp4-mtp0-current-piecewise-graph-a5-resources.sh"
expected_watchdog=8cd82a5fd68ceaaf2fee28232996c24051c53902f247eebc50d623a667c1e40f
classifier=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/classify-q38-piecewise-graph-a5-kernel-journal.py
expected_classifier=440d7d0636bef8b5baf9bd5603ced988e22fe64c7df912ed15e55561aea8ea16
resource_dir=/var/tmp/q38-piecewise-graph-a5-resource
resource_archive_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt5-resource-archive
inner_evidence=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt5-supervisor
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt5
cache_dir=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt5
compile_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt5-compile
rpc_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt5-rpc
state=/tmp/q38-mtp0-current-piecewise-graph-a5
outer_state=/tmp/q38-mtp0-current-piecewise-graph-a5-swap64
swapfile=/var/tmp/q38-piecewise-graph-a5-64g.swap
sudo_password=/home/steve/SUDOPASSWORD.txt
swap_bytes=68719476736
expected_swap_kib=67108860
precreate_floor_bytes=111669149696
root_floor_bytes=42949672960
mem_floor_kib=12582912
swapoff_mem_reserve_kib=16777216
derived_supervisor="${resource_dir}/derived-supervisor.sh"
expected_derived=a3344488b98afc4d7ce7010a3da36a58ec6fbeee38e0f9061d188e08baf03aac
staged_wrapper="${resource_dir}/$(basename -- "$wrapper")"
staged_client="${resource_dir}/$(basename -- "$client")"
staged_wrapper_identity=""
staged_client_identity=""
derived_supervisor_identity=""
inner_pid=""
watchdog_pid=""
swap_created=0
swap_active=0
swap_object=""
swap_identity=""
resource_fault=0
started=0
finished=0
journal_start_epoch=$(date +%s)
outer_deadline_epoch=$((journal_start_epoch + 7500))

write_atomic() {
  local path=$1 value=$2 tmp="${1}.tmp.$$"
  printf '%s\n' "$value" >"$tmp"
  mv "$tmp" "$path"
}

sudo_do() {
  /usr/bin/timeout --signal=TERM --kill-after=10s 180s \
    /usr/bin/sudo -S -p '' -- "$@" <"$sudo_password"
}

swap_stat() {
  stat -c '%d:%i:%u:%g:%s:%a' -- "$swapfile"
}

swap_object_stat() {
  stat -c '%d:%i' -- "$swapfile"
}

staged_stat() {
  stat -c '%d:%i:%u:%g:%s:%a' -- "$1"
}

validate_staged_inputs() {
  [[ -f "$staged_wrapper" && ! -L "$staged_wrapper" && \
     -f "$staged_client" && ! -L "$staged_client" && \
     -f "$derived_supervisor" && ! -L "$derived_supervisor" ]] || return 1
  [[ "$(staged_stat "$staged_wrapper")" == "$staged_wrapper_identity" && \
     "$(staged_stat "$staged_client")" == "$staged_client_identity" && \
     "$(staged_stat "$derived_supervisor")" == "$derived_supervisor_identity" ]] || return 1
  [[ "$(sha256sum "$staged_wrapper" | cut -d' ' -f1)" == "$expected_wrapper" && \
     "$(sha256sum "$staged_client" | cut -d' ' -f1)" == "$expected_client" && \
     "$(sha256sum "$derived_supervisor" | cut -d' ' -f1)" == "$expected_derived" ]] || return 1
  [[ "$(stat -c '%a' -- "$staged_wrapper")" == 500 && \
     "$(stat -c '%a' -- "$staged_client")" == 500 && \
     "$(stat -c '%a' -- "$derived_supervisor")" == 500 && \
     "$(stat -c '%u:%g' -- "$staged_wrapper")" == 1000:1000 && \
     "$(stat -c '%u:%g' -- "$staged_client")" == 1000:1000 && \
     "$(stat -c '%u:%g' -- "$derived_supervisor")" == 1000:1000 ]]
}

validate_swapfile() {
  [[ -f "$swapfile" && ! -L "$swapfile" ]] || return 1
  [[ "$(swap_object_stat)" == "$swap_object" ]]
}

latch_resource_fault() {
  local reason=$1
  resource_fault=1
  write_atomic "${resource_dir}/resource.failed" "$reason"
  write_atomic "${state}.failed" "FAIL graph attempt-5 outer resource guard: ${reason}"
}

wait_inner_bounded() {
  local limit=$1 tick
  for tick in $(seq 1 "$limit"); do
    kill -0 "$inner_pid" 2>/dev/null || return 0
    sleep 1
  done
  return 1
}

validate_swapfile_allocated() {
  local blocks block_size
  validate_swapfile || return 1
  read -r blocks block_size < <(stat -c '%b %B' -- "$swapfile")
  [[ "$blocks" =~ ^[0-9]+$ && "$block_size" =~ ^[0-9]+$ ]] && \
    (( blocks * block_size >= swap_bytes )) || return 1
  [[ "$(swap_stat)" == "$swap_identity" ]]
}

stop_watchdog() {
  set +e
  if [[ "$watchdog_pid" =~ ^[1-9][0-9]*$ ]] && kill -0 "$watchdog_pid" 2>/dev/null; then
    write_atomic "${resource_dir}/watchdog.stop" 'STOP after inner supervisor exit'
    for _ in $(seq 1 10); do
      kill -0 "$watchdog_pid" 2>/dev/null || break
      sleep 1
    done
    kill -TERM "$watchdog_pid" 2>/dev/null || true
  fi
  [[ -z "$watchdog_pid" ]] || wait "$watchdog_pid" 2>/dev/null || true
  set -e
}

cleanup_swap() {
  local current used mem_available required
  set +e
  [[ -d "$resource_dir" ]] && : >"${resource_dir}/swap-cleanup.log"
  if (( swap_created == 1 )); then
    current=$(swap_stat 2>/dev/null || true)
    write_atomic "${resource_dir}/swapfile-identity-before-swapoff.txt" "$current"
    if ! validate_swapfile; then
      printf 'REFUSED: swapfile identity changed; no swapoff or removal\n' >>"${resource_dir}/swap-cleanup.log"
      set -e
      return 1
    fi
  fi
  if awk -v path="$swapfile" '$1 == path {found=1} END {exit !found}' /proc/swaps; then
    swap_active=1
    if ! validate_swapfile_allocated; then
      printf 'REFUSED: active swapfile identity/allocation changed; no swapoff or removal\n' >>"${resource_dir}/swap-cleanup.log"
      set -e
      return 1
    fi
    used=$(awk -v path="$swapfile" '$1 == path {print $4}' /proc/swaps)
    mem_available=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    required=$((used + swapoff_mem_reserve_kib))
    if [[ ! "$used" =~ ^[0-9]+$ || ! "$mem_available" =~ ^[0-9]+$ || mem_available -lt required ]]; then
      printf 'REFUSED: unsafe swapoff admission (used=%s KiB MemAvailable=%s KiB required=%s KiB); active file preserved\n' \
        "$used" "$mem_available" "$required" >>"${resource_dir}/swap-cleanup.log"
      set -e
      return 1
    fi
    if ! /usr/bin/timeout --signal=TERM --kill-after=30s 900s /usr/bin/sudo -S -p '' -- \
      /sbin/swapoff -- "$swapfile" <"$sudo_password" >>"${resource_dir}/swap-cleanup.log" 2>&1; then
      printf 'REFUSED: swapoff failed; active file preserved\n' >>"${resource_dir}/swap-cleanup.log"
      set -e
      return 1
    fi
    swap_active=0
    current=$(swap_stat 2>/dev/null || true)
    write_atomic "${resource_dir}/swapfile-identity-after-swapoff.txt" "$current"
    if [[ "$current" != "$swap_identity" ]] || ! validate_swapfile_allocated; then
      printf 'REFUSED: post-swapoff file identity/allocation changed; file preserved\n' >>"${resource_dir}/swap-cleanup.log"
      set -e
      return 1
    fi
  fi
  if (( swap_created == 1 )); then
    current=$(swap_stat 2>/dev/null || true)
    if ! validate_swapfile; then
      printf 'REFUSED: post-swapoff file identity changed; file preserved\n' >>"${resource_dir}/swap-cleanup.log"
      set -e
      return 1
    fi
    if ! sudo_do /usr/bin/unlink -- "$swapfile" >>"${resource_dir}/swap-cleanup.log" 2>&1; then
      printf 'REFUSED: exact swapfile removal failed\n' >>"${resource_dir}/swap-cleanup.log"
      set -e
      return 1
    fi
    swap_created=0
  fi
  awk 'NR > 1 {print $1, $2, $3, $5}' /proc/swaps >"${resource_dir}/swaps-restored-layout.txt"
  if ! cmp -s "${resource_dir}/swaps-before-layout.txt" "${resource_dir}/swaps-restored-layout.txt"; then
    printf 'REFUSED: original swap layout was not exactly restored\n' >>"${resource_dir}/swap-cleanup.log"
    set -e
    return 1
  fi
  printf 'PASS: temporary swap inactive and exact file removed\n' >>"${resource_dir}/swap-cleanup.log"
  set -e
  return 0
}

capture_resources() {
  local journal_rc
  mkdir -p "$resource_dir"
  cp /proc/meminfo "${resource_dir}/meminfo-final.txt" 2>/dev/null || true
  cp /proc/swaps "${resource_dir}/swaps-final.txt" 2>/dev/null || true
  df -PB1 /var/tmp >"${resource_dir}/root-filesystem-final.txt" 2>&1 || true
  if journalctl -k --since "@${journal_start_epoch}" --no-pager \
    >"${resource_dir}/kernel-journal-final.log" 2>"${resource_dir}/kernel-journal-final.err"; then
    journal_rc=0
  else
    journal_rc=$?
  fi
  write_atomic "${resource_dir}/kernel-journal-final.rc" "$journal_rc"
  if [[ -s "${resource_dir}/resource-watchdog.tsv" ]]; then
    awk -F '\t' 'NR>1 {if ($7>max) max=$7; last=$7; rows++} END {printf "samples=%d\nmax_temp_swap_used_kib=%d\nfinal_temp_swap_used_kib=%d\n",rows,max,last}' \
      "${resource_dir}/resource-watchdog.tsv" >"${resource_dir}/swap-traffic-summary.txt"
  fi
}

emergency_exit() {
  local rc=$? inner_stopped=1
  (( rc != 0 )) || rc=70
  if (( started == 1 && finished == 0 )); then
    set +e
    if [[ "$inner_pid" =~ ^[1-9][0-9]*$ ]] && kill -0 "$inner_pid" 2>/dev/null; then
      kill -TERM "$inner_pid" 2>/dev/null || true
      if ! wait_inner_bounded 360; then
        latch_resource_fault 'inner supervisor did not exit within 360 seconds after emergency TERM'
        inner_stopped=0
      fi
    fi
    if (( inner_stopped == 1 )) && [[ "$inner_pid" =~ ^[1-9][0-9]*$ ]]; then
      wait "$inner_pid" 2>/dev/null || true
    fi
    stop_watchdog
    if (( inner_stopped == 1 )); then
      cleanup_swap || rc=70
    else
      printf 'REFUSED: inner supervisor remains live; temporary swap preserved\n' \
        >>"${resource_dir}/swap-cleanup.log"
      rc=70
    fi
    write_atomic "${outer_state}.rc" "$rc"
    capture_resources
    write_atomic "${resource_dir}/final.rc" "$rc"
    set -e
  fi
}
trap emergency_exit EXIT
trap 'exit 130' INT TERM HUP

[[ $# == 0 ]] || { printf 'FAIL: attempt-5 swap supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$source_supervisor" | cut -d' ' -f1)" == "$expected_source" ]] || { printf 'FAIL: attempt-1 supervisor source changed\n' >&2; exit 1; }
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]] || { printf 'FAIL: attempt-5 wrapper changed\n' >&2; exit 1; }
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]] || { printf 'FAIL: attempt-5 client adapter changed\n' >&2; exit 1; }
[[ "$(sha256sum "$watchdog" | cut -d' ' -f1)" == "$expected_watchdog" ]] || { printf 'FAIL: attempt-5 watchdog changed\n' >&2; exit 1; }
printf '%s  %s\n' "$expected_classifier" "$classifier" | sha256sum -c - >/dev/null || { printf 'FAIL: journal classifier hash changed\n' >&2; exit 1; }
[[ -f "$sudo_password" && ! -L "$sudo_password" && -r "$sudo_password" && \
   "$(stat -c '%U:%a:%F' "$sudo_password")" == 'steve:600:regular file' ]] || { printf 'FAIL: sudo password file identity/permissions invalid\n' >&2; exit 1; }
for path in "$resource_dir" "$resource_archive_dir" "$inner_evidence" "$run_dir" "$cache_dir" "$compile_dir" "$rpc_dir" \
  "$swapfile" "${outer_state}.pid" "${outer_state}.rc" "${state}.pid" "${state}.child.pid" \
  "${state}.launcher.pid" "${state}.server.pid" "${state}.server.pgid" "${state}.rc" \
  "${state}.stop" "${state}.failed" "${state}.deadline-epoch"; do
  [[ ! -e "$path" ]] || { printf 'FAIL: refusing to reuse %s\n' "$path" >&2; exit 1; }
done
! awk -v path="$swapfile" '$1 == path {found=1} END {exit !found}' /proc/swaps || { printf 'FAIL: target swap path already active\n' >&2; exit 1; }
read -r mount_target mount_source mount_type mount_options < <(findmnt -no TARGET,SOURCE,FSTYPE,OPTIONS -T /var/tmp)
[[ "$mount_target" == / && "$mount_source" == /dev/nvme0n1p2 && "$mount_type" == ext4 && ",${mount_options}," == *,rw,* ]] || {
  printf 'FAIL: /var/tmp must resolve to the frozen root ext4 filesystem\n' >&2
  exit 1
}
root_available=$(df -PB1 /var/tmp | awk 'NR==2 {print $4}')
[[ "$root_available" =~ ^[0-9]+$ ]] && (( root_available >= precreate_floor_bytes )) || {
  printf 'FAIL: need at least 64 GiB plus the 40-GiB root floor before swap creation\n' >&2
  exit 1
}

mkdir -m 0700 "$resource_dir"
write_atomic "${resource_dir}/journal-start-epoch.txt" "$journal_start_epoch"
write_atomic "${outer_state}.pid" "$$"
write_atomic "${outer_state}.deadline-epoch" "$outer_deadline_epoch"
cp /proc/meminfo "${resource_dir}/meminfo-before.txt"
cp /proc/swaps "${resource_dir}/swaps-before.txt"
awk 'NR > 1 {print $1, $2, $3, $5}' /proc/swaps >"${resource_dir}/swaps-before-layout.txt"
df -PB1 /var/tmp >"${resource_dir}/root-filesystem-before.txt"
findmnt -no TARGET,SOURCE,FSTYPE,OPTIONS -T /var/tmp >"${resource_dir}/root-mount.txt"
started=1

timeout 15s /usr/bin/sudo -S -p '' -v <"$sudo_password" >"${resource_dir}/sudo-auth.log" 2>&1
(umask 077; set -o noclobber; : >"$swapfile")
swap_object=$(swap_object_stat)
swap_created=1
sudo_do /usr/bin/chown root:root -- "$swapfile"
sudo_do /usr/bin/chmod 0600 -- "$swapfile"
[[ "$(swap_object_stat)" == "$swap_object" && "$(stat -c '%u:%g:%a' -- "$swapfile")" == '0:0:600' ]] || {
  printf 'FAIL: swapfile ownership or object identity changed during creation\n' >&2
  exit 1
}
sudo_do /usr/bin/fallocate -l "$swap_bytes" -- "$swapfile" >"${resource_dir}/fallocate.log" 2>&1
swap_identity=$(swap_stat)
[[ "$(swap_object_stat)" == "$swap_object" ]] || { printf 'FAIL: swapfile object changed during allocation\n' >&2; exit 1; }
[[ "$swap_identity" =~ ^[0-9]+:[0-9]+:0:0:${swap_bytes}:600$ ]] || { printf 'FAIL: created swapfile identity invalid\n' >&2; exit 1; }
validate_swapfile_allocated || { printf 'FAIL: swapfile is not a fully allocated regular non-symlink file\n' >&2; exit 1; }
write_atomic "${resource_dir}/swapfile-identity-after-create.txt" "$swap_identity"
sudo_do /sbin/mkswap "$swapfile" >"${resource_dir}/mkswap.log" 2>&1
[[ "$(swap_stat)" == "$swap_identity" ]] && validate_swapfile_allocated || { printf 'FAIL: swapfile identity/allocation changed after mkswap\n' >&2; exit 1; }
write_atomic "${resource_dir}/swapfile-identity-after-mkswap.txt" "$(swap_stat)"
sudo_do /sbin/swapon -p -1 -- "$swapfile" >"${resource_dir}/swapon.log" 2>&1
swap_active=1
swap_row=$(awk -v path="$swapfile" '$1 == path {print $3 " " $4 " " $5}' /proc/swaps)
[[ "$swap_row" =~ ^${expected_swap_kib}\ [0-9]+\ -1$ ]] || { printf 'FAIL: temporary swap activation identity invalid: %s\n' "$swap_row" >&2; exit 1; }
root_available=$(df -PB1 /var/tmp | awk 'NR==2 {print $4}')
mem_available=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
(( root_available >= root_floor_bytes && mem_available >= mem_floor_kib )) || { printf 'FAIL: post-activation resource floor failed\n' >&2; exit 1; }
cp /proc/swaps "${resource_dir}/swaps-active.txt"
awk -v path="$swapfile" 'NR > 1 && $1 != path {print $1, $2, $3, $5}' /proc/swaps >"${resource_dir}/swaps-active-base-layout.txt"
cmp -s "${resource_dir}/swaps-before-layout.txt" "${resource_dir}/swaps-active-base-layout.txt" || { printf 'FAIL: pre-existing swap layout changed during activation\n' >&2; exit 1; }
cp /proc/meminfo "${resource_dir}/meminfo-active.txt"
df -PB1 /var/tmp >"${resource_dir}/root-filesystem-active.txt"

sed \
  -e 's/supervise-tp4-mtp0-current-piecewise-graph-a1/supervise-tp4-mtp0-current-piecewise-graph-a5/g' \
  -e 's/launch-tp4-mtp0-current-piecewise-graph-a1/launch-tp4-mtp0-current-piecewise-graph-a5/g' \
  -e 's/run-tp4-mtp0-current-piecewise-graph-a1-client/run-tp4-mtp0-current-piecewise-graph-a5-client/g' \
  -e 's/52642fdff6a4cd208241aaee0ad3bc3c049c1b46915457dec985ab23ebeb3ec5/19f08177b2d12bd25e9b2c21f96fb5ee81aec7b8bd6c8c8e37af00b289631487/g' \
  -e 's/5886f5ba6127826f1122bc8ac26d4c1b328d9ab34674051e50cb5d985dbdaaaf/8da39d3c001651c05ca1d534c8e80f7f326207a61ead89a3be1499e1c14203b9/g' \
  -e 's/q38-mtp0-current-piecewise-graph-a1/q38-mtp0-current-piecewise-graph-a5/g' \
  -e 's/attempt1/attempt5/g' \
  -e 's/19674/19679/g' \
  "$source_supervisor" >"$derived_supervisor"
chmod 0500 "$derived_supervisor"
[[ "$(sha256sum "$derived_supervisor" | cut -d' ' -f1)" == "$expected_derived" ]] || { printf 'FAIL: derived attempt-5 supervisor hash mismatch\n' >&2; exit 1; }
derived_supervisor_identity=$(staged_stat "$derived_supervisor")
[[ "$(stat -c '%u:%g:%a' -- "$derived_supervisor")" == 1000:1000:500 ]] || {
  printf 'FAIL: derived supervisor owner or mode is not exact ext4 1000:1000:0500\n' >&2
  exit 1
}

[[ ! -e "$staged_wrapper" && ! -e "$staged_client" ]] || {
  printf 'FAIL: staged wrapper/client paths are not fresh\n' >&2
  exit 1
}
/usr/bin/install -m 0500 -- "$wrapper" "$staged_wrapper"
/usr/bin/install -m 0500 -- "$client" "$staged_client"
staged_wrapper_identity=$(staged_stat "$staged_wrapper")
staged_client_identity=$(staged_stat "$staged_client")
validate_staged_inputs || {
  printf 'FAIL: staged wrapper/client identity, mode, or hash mismatch\n' >&2
  exit 1
}
{
  printf 'wrapper_path=%s\nwrapper_sha256=%s\nwrapper_identity=%s\n' \
    "$staged_wrapper" "$expected_wrapper" "$staged_wrapper_identity"
  printf 'client_path=%s\nclient_sha256=%s\nclient_identity=%s\n' \
    "$staged_client" "$expected_client" "$staged_client_identity"
  printf 'derived_supervisor_path=%s\nderived_supervisor_sha256=%s\nderived_supervisor_identity=%s\n' \
    "$derived_supervisor" "$expected_derived" "$derived_supervisor_identity"
  printf 'declared_post_closeout_archive=%s\n' "$resource_archive_dir"
} >"${resource_dir}/staged-inner-inputs.txt"

/bin/bash "$derived_supervisor" &
inner_pid=$!
write_atomic "${outer_state}.inner.pid" "$inner_pid"
for _ in $(seq 1 100); do
  [[ -s "${state}.pid" ]] && break
  kill -0 "$inner_pid" 2>/dev/null || break
  sleep .2
done
[[ "$(cat "${state}.pid" 2>/dev/null || true)" == "$inner_pid" ]] || { printf 'FAIL: derived supervisor did not establish exact state\n' >&2; exit 70; }
"$watchdog" "$$" &
watchdog_pid=$!
write_atomic "${outer_state}.watchdog.pid" "$watchdog_pid"
for _ in $(seq 1 100); do
  [[ -s "${resource_dir}/watchdog.heartbeat-epoch" ]] && break
  kill -0 "$watchdog_pid" 2>/dev/null || break
  sleep .1
done
heartbeat_epoch=$(cat "${resource_dir}/watchdog.heartbeat-epoch" 2>/dev/null || true)
[[ "$heartbeat_epoch" =~ ^[1-9][0-9]*$ ]] && (( $(date +%s) - heartbeat_epoch <= 10 )) || {
  write_atomic "${state}.failed" 'FAIL graph attempt-5 resource watchdog heartbeat did not start'
  exit 70
}

while kill -0 "$inner_pid" 2>/dev/null; do
  if ! validate_staged_inputs; then
    latch_resource_fault 'staged wrapper/client identity, mode, or hash changed'
    kill -TERM "$inner_pid" 2>/dev/null || true
    break
  fi
  if (( $(date +%s) >= outer_deadline_epoch )); then
    latch_resource_fault 'model/inner occupancy exceeded 7500 seconds'
    kill -TERM "$inner_pid" 2>/dev/null || true
    break
  fi
  if ! kill -0 "$watchdog_pid" 2>/dev/null; then
    [[ -e "${resource_dir}/resource.failed" ]] || \
      latch_resource_fault 'resource watchdog exited unexpectedly'
    resource_fault=1
    kill -TERM "$inner_pid" 2>/dev/null || true
    break
  fi
  heartbeat_epoch=$(cat "${resource_dir}/watchdog.heartbeat-epoch" 2>/dev/null || true)
  if [[ ! "$heartbeat_epoch" =~ ^[1-9][0-9]*$ ]] || (( $(date +%s) - heartbeat_epoch > 10 )); then
    latch_resource_fault 'resource watchdog heartbeat stale beyond 10 seconds'
    kill -TERM "$inner_pid" 2>/dev/null || true
    break
  fi
  sleep 2
done
inner_wait_timed_out=0
if ! wait_inner_bounded 360; then
  latch_resource_fault 'inner supervisor did not exit within 360 seconds after TERM/stop'
  inner_wait_timed_out=1
  inner_rc=70
else
  set +e
  wait "$inner_pid"
  inner_rc=$?
  set -e
fi
if ! validate_staged_inputs; then
  latch_resource_fault 'staged wrapper/client failed terminal identity check'
fi
stop_watchdog
terminal_heartbeat=$(cat "${resource_dir}/watchdog.heartbeat-epoch" 2>/dev/null || true)
if [[ "$(cat "${resource_dir}/watchdog.rc" 2>/dev/null || true)" != 0 ]] || \
   [[ ! "$terminal_heartbeat" =~ ^[1-9][0-9]*$ ]] || \
   (( $(date +%s) - terminal_heartbeat > 15 )); then
  if [[ ! -e "${resource_dir}/resource.failed" ]]; then
    latch_resource_fault 'resource watchdog lacked a controlled stop or fresh terminal heartbeat'
  else
    resource_fault=1
  fi
fi
cleanup_rc=0
if (( inner_wait_timed_out == 0 )); then
  cleanup_swap || cleanup_rc=$?
else
  printf 'REFUSED: inner supervisor remains live; temporary swap preserved\n' \
    >>"${resource_dir}/swap-cleanup.log"
  cleanup_rc=70
fi
capture_resources
rc=$inner_rc
(( resource_fault == 0 )) || rc=70
[[ ! -e "${resource_dir}/resource.failed" ]] || rc=70
(( cleanup_rc == 0 )) || rc=70
[[ ! -e "$swapfile" ]] || rc=70
! awk -v path="$swapfile" '$1 == path {found=1} END {exit !found}' /proc/swaps || rc=70
[[ "$(cat "${resource_dir}/kernel-journal-final.rc" 2>/dev/null)" == 0 ]] || rc=70
"$classifier" "${resource_dir}/kernel-journal-final.log" \
  "${resource_dir}/root-nvme-corrected-events-final.log" || rc=70
write_atomic "${outer_state}.rc" "$rc"
write_atomic "${resource_dir}/inner-supervisor.rc" "$inner_rc"
write_atomic "${resource_dir}/final.rc" "$rc"
finished=1
exit "$rc"
