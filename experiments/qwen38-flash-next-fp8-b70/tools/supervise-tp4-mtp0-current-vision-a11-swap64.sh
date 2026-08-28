#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
outer_script="${script_dir}/$(basename -- "${BASH_SOURCE[0]}")"
source_supervisor="${script_dir}/supervise-tp4-mtp0-current-vision-a11-inner.sh"
expected_source=7906ec765c3bf6f909959f6866f4579f8654b383724d871ee1bf6d83133b4866
wrapper="${script_dir}/launch-tp4-mtp0-current-vision-a11.sh"
expected_wrapper=ea479239faf783956dbfa486889d85edf4817000a584616d297706189dc44a3e
client="${script_dir}/run-tp4-mtp0-current-vision-a11-client.sh"
expected_client=b9a4651b347c630bd0573a9f34b2ceb0d2cf1cc5e526f9cee8d496108fda2c20
watchdog="${script_dir}/watch-tp4-mtp0-current-vision-a11-resources.sh"
expected_watchdog=048481d4d4bfd2092f6fb00a7a9005b1fce027943d6fc7d7aace3a872cdaded6
classifier=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/classify-q38-piecewise-graph-a5-kernel-journal.py
expected_classifier=440d7d0636bef8b5baf9bd5603ced988e22fe64c7df912ed15e55561aea8ea16
runtime_classifier="${script_dir}/classify-q38-runtime-conflicts.py"
expected_runtime_classifier=ecd18d133eef946bacf2750717bc458eca8e64dc1d97beabe060bdf314bf2ab3
runtime_classifier_test="${script_dir}/test-q38-runtime-conflict-classifier.sh"
expected_runtime_classifier_test=c30a1d552388c10df0e61f882b633cf57304fd76e40eadc886676b78b27ff63e
resource_policy_test="${script_dir}/test-q38-vision-a11-resource-policy.sh"
expected_resource_policy_test=f95956c7cb6f916c1e0c980f596daedba5776005790757c90c4166e98e29f2df
attempt10_closeout="${script_dir}/../data/20260828-tp4-mtp0-fixed-vision-attempt10-administrative-closeout.json"
expected_attempt10_closeout=0862f156b15d3f72d295b9966f2fb5e9ce30d1d9494946981b718a22efc2732d
attempt10_manifest="${script_dir}/../data/20260828-tp4-mtp0-fixed-vision-attempt10-primary-evidence.sha256"
expected_attempt10_manifest=68470e550fcdbb667137bf5da8402647995dddc69bf06595a7b07193556b80bd
expected_attempt10_manifest_entries=47
resource_dir=/var/tmp/q38-vision-a11-resource
resource_archive_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt11-resource-archive
inner_evidence=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt11-supervisor
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt11
cache_dir=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt11
compile_dir=/tmp/q38v-a11-c
rpc_dir=/tmp/q38v-a11-r
state=/tmp/q38-mtp0-current-vision-a11
outer_state=/tmp/q38-mtp0-current-vision-a11-swap64
swapfile=/var/tmp/q38-vision-a11-64g.swap
sudo_password=/home/steve/SUDOPASSWORD.txt
swap_bytes=68719476736
expected_swap_kib=67108860
precreate_floor_bytes=111669149696
root_floor_bytes=42949672960
mem_floor_kib=10485760
swapoff_mem_reserve_kib=16777216
derived_supervisor="${resource_dir}/derived-supervisor.sh"
expected_derived=038f0abe50639b514b2089353bd1a2f864edc0ad12efa282e8c7da1b8f809722
staged_wrapper="${resource_dir}/$(basename -- "$wrapper")"
staged_client="${resource_dir}/$(basename -- "$client")"
staged_wrapper_identity=""
staged_client_identity=""
derived_supervisor_identity=""
inner_pid=""
watchdog_pid=""
watchdog_starttime=""
swap_created=0
swap_active=0
swap_object=""
swap_identity=""
resource_fault=0
started=0
finished=0
journal_start_epoch=$(date +%s)
outer_deadline_epoch=$((journal_start_epoch + 16200))
outer_starttime=$(awk '{print $22}' "/proc/$$/stat")
server_group=""
workers_remain=0
terminal_absence_verified=0
user_active_epoch=""

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

scan_runtime_conflicts() {
  local output=$1
  "$runtime_classifier" \
    --supervisor-pid "$$" \
    --supervisor-starttime "$outer_starttime" \
    --supervisor-script "$outer_script" \
    >"$output" 2>"${output%.json}.err"
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
  [[ -e "${resource_dir}/resource.failed" ]] || write_atomic "${resource_dir}/resource.failed" "$reason"
  [[ -e "${state}.failed" ]] || write_atomic "${state}.failed" "FAIL vision attempt-11 outer resource guard: ${reason}"
  printf '%s\t%s\n' "$(date +%s)" "$reason" >>"${resource_dir}/outer-faults.log"
}

monotonic_seconds() {
  awk '{print int($1)}' /proc/uptime
}

wait_pid_monotonic() {
  local pid=$1 seconds=$2 deadline
  deadline=$(( $(monotonic_seconds) + seconds ))
  while [[ -e "/proc/${pid}" ]] && [[ "$(awk '{print $3}' "/proc/${pid}/stat" 2>/dev/null || true)" != Z ]]; do
    (( $(monotonic_seconds) < deadline )) || return 1
    sleep .2
  done
  return 0
}

pid_live_non_z() {
  local pid=$1 state_value
  [[ "$pid" =~ ^[1-9][0-9]*$ && -e "/proc/${pid}" ]] || return 1
  state_value=$(awk '{print $3}' "/proc/${pid}/stat" 2>/dev/null || true)
  [[ -n "$state_value" && "$state_value" != Z ]]
}

validate_watchdog_identity() {
  local current_starttime command
  pid_live_non_z "$watchdog_pid" || return 0
  current_starttime=$(awk '{print $22}' "/proc/${watchdog_pid}/stat" 2>/dev/null || true)
  command=$(tr '\0' ' ' <"/proc/${watchdog_pid}/cmdline" 2>/dev/null || true)
  [[ "$watchdog_starttime" =~ ^[1-9][0-9]*$ && \
     "$current_starttime" == "$watchdog_starttime" && \
     "$command" == *"$watchdog"* ]]
}

server_group_live() {
  [[ "$server_group" =~ ^[1-9][0-9]*$ ]] || return 1
  ps -eo pgid=,stat= | awk -v group="$server_group" \
    '$1 == group && $2 !~ /^Z/ {found=1} END {exit !found}'
}

resolve_owned_server_group() {
  local pid pgid command
  pid=$(cat "${state}.server.pid" 2>/dev/null || cat "${run_dir}/server.pid" 2>/dev/null || true)
  pgid=$(cat "${state}.server.pgid" 2>/dev/null || true)
  [[ "$pid" =~ ^[1-9][0-9]*$ && -e "/proc/${pid}" ]] || return 1
  command=$(tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null || true)
  [[ "$command" == *'vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8'* && \
     "$command" == *'--port 19690'* && "$command" == *'--max-model-len 512'* && \
     "$command" == *'--enforce-eager'* && "$command" == *'--limit-mm-per-prompt'* && \
     "$command" == *'--mm-processor-cache-gb 0'* && \
     "$command" == *'--mm-encoder-tp-mode weights'* && \
     "$command" != *'--language-model-only'* && \
     "$command" != *'--speculative-config'* ]] || return 1
  if [[ ! "$pgid" =~ ^[1-9][0-9]*$ ]]; then
    pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
  fi
  [[ "$pgid" == "$pid" ]] || return 1
  server_group=$pgid
  {
    printf 'server_pid=%s\nserver_pgid=%s\ncommand=%s\n' "$pid" "$pgid" "$command"
    ps -eo pid=,ppid=,pgid=,stat=,args= | awk -v group="$pgid" '$3 == group'
  } >"${resource_dir}/direct-server-group-target.txt"
}

terminate_owned_server_group() {
  local reason=$1 deadline scan_rc
  if ! resolve_owned_server_group; then
    set +e
    scan_runtime_conflicts "${resource_dir}/unresolved-stop-runtime-conflicts.json"
    scan_rc=$?
    set -e
    if (( scan_rc == 0 )) && jq -e '.schema == "neural.download.q38-runtime-conflict-scan.v3" and
      .status == "clear" and
      (.conflicts | length) == 0 and (.errors | length) == 0 and
      (.vanished_races | type) == "array" and
      all(.vanished_races[]; .classification == "vanished_race" and .field == "stat") and
      .binding.supervisor.pid > 0 and (.scanned_processes | length) > 0' \
      "${resource_dir}/unresolved-stop-runtime-conflicts.json" >/dev/null 2>&1; then
      return 0
    fi
    workers_remain=1
    latch_resource_fault \
      "cannot verify server process group and structured runtime scan was non-clear rc=${scan_rc}: ${reason}"
    return 1
  fi
  write_atomic "${resource_dir}/direct-stop-reason.txt" "$reason"
  kill -TERM -- "-${server_group}" 2>/dev/null || true
  deadline=$(( $(monotonic_seconds) + 12 ))
  while server_group_live && (( $(monotonic_seconds) < deadline )); do sleep .2; done
  if server_group_live; then
    write_atomic "${resource_dir}/direct-stop-kill-used.txt" \
      "KILL after monotonic 12-second TERM bound; group=${server_group}"
    kill -KILL -- "-${server_group}" 2>/dev/null || true
    deadline=$(( $(monotonic_seconds) + 8 ))
    while server_group_live && (( $(monotonic_seconds) < deadline )); do sleep .2; done
  fi
  if server_group_live; then
    workers_remain=1
    latch_resource_fault "server process group ${server_group} remained after bounded TERM/KILL"
    ps -eo pid=,ppid=,pgid=,stat=,args= | awk -v group="$server_group" '$3 == group' \
      >"${resource_dir}/server-group-remains.txt"
    return 1
  fi
  write_atomic "${resource_dir}/direct-server-group-stopped.txt" \
    "PASS group=${server_group} no non-zombie members after bounded TERM/KILL"
}

terminate_inner_bounded() {
  local pid command path failed=0
  local -a control_pids=()
  for path in "${state}.launcher.pid" "${state}.child.pid" "${outer_state}.inner.pid"; do
    pid=$(cat "$path" 2>/dev/null || true)
    [[ "$pid" =~ ^[1-9][0-9]*$ && "$pid" != "$$" ]] || continue
    [[ -e "/proc/${pid}" ]] || continue
    command=$(tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null || true)
    [[ "$command" == *'q38-vision-a11-resource'* || \
       "$command" == *'vision-a11'* || \
       "$command" == *'eager-mtp0-vision-512-r1-attempt11'* ]] || {
      workers_remain=1
      latch_resource_fault "controller PID ${pid} identity mismatch; refusing signal"
      return 1
    }
    control_pids+=("$pid")
  done
  for pid in "${control_pids[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
  for pid in "${control_pids[@]}"; do
    wait_pid_monotonic "$pid" 8 || true
  done
  for pid in "${control_pids[@]}"; do
    if [[ -e "/proc/${pid}" ]] && [[ "$(awk '{print $3}' "/proc/${pid}/stat" 2>/dev/null || true)" != Z ]]; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
  for pid in "${control_pids[@]}"; do
    if ! wait_pid_monotonic "$pid" 5; then
      failed=1
      workers_remain=1
    fi
  done
  (( failed == 0 )) || {
    latch_resource_fault 'controller tree remained after bounded TERM/KILL'
    return 1
  }
}

terminal_server_group_absent() {
  local saved_group scan_rc
  terminal_absence_verified=0
  saved_group=$(cat "${state}.server.pgid" 2>/dev/null || true)
  if [[ -n "$saved_group" && ! "$saved_group" =~ ^[1-9][0-9]*$ ]]; then
    workers_remain=1
    latch_resource_fault 'terminal server PGID receipt is malformed'
    return 1
  fi
  if [[ "$saved_group" =~ ^[1-9][0-9]*$ ]]; then
    server_group=$saved_group
    if server_group_live; then
      workers_remain=1
      ps -eo pid=,ppid=,pgid=,stat=,args= | awk -v group="$server_group" '$3 == group' \
        >"${resource_dir}/terminal-server-group-remains.txt"
      latch_resource_fault "terminal server process group ${server_group} remains"
      return 1
    fi
  fi
  set +e
  scan_runtime_conflicts "${resource_dir}/terminal-runtime-conflicts.json"
  scan_rc=$?
  set -e
  if (( scan_rc != 0 )) || ! jq -e '.schema == "neural.download.q38-runtime-conflict-scan.v3" and
    .status == "clear" and
    (.conflicts | length) == 0 and (.errors | length) == 0 and
    (.vanished_races | type) == "array" and
    all(.vanished_races[]; .classification == "vanished_race" and .field == "stat") and
    .binding.supervisor.pid > 0 and (.scanned_processes | length) > 0' \
    "${resource_dir}/terminal-runtime-conflicts.json" >/dev/null 2>&1; then
    workers_remain=1
    latch_resource_fault "terminal structured runtime scan was non-clear rc=${scan_rc}"
    return 1
  fi
  terminal_absence_verified=1
  write_atomic "${resource_dir}/terminal-server-group-absent.txt" \
    "PASS saved_group=${saved_group:-absent} has no non-zombie members"
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
  local stopped=0
  set +e
  if ! validate_watchdog_identity; then
    latch_resource_fault 'resource watchdog PID/starttime/command identity changed; refusing signal'
    set -e
    return 1
  fi
  if pid_live_non_z "$watchdog_pid"; then
    write_atomic "${resource_dir}/watchdog.stop" 'STOP after inner supervisor exit'
    wait_pid_monotonic "$watchdog_pid" 5 || true
  fi
  if pid_live_non_z "$watchdog_pid"; then
    kill -TERM "$watchdog_pid" 2>/dev/null || true
    wait_pid_monotonic "$watchdog_pid" 5 || true
  fi
  if pid_live_non_z "$watchdog_pid"; then
    kill -KILL "$watchdog_pid" 2>/dev/null || true
    wait_pid_monotonic "$watchdog_pid" 3 || true
  fi
  if pid_live_non_z "$watchdog_pid"; then
    latch_resource_fault 'resource watchdog remained after monotonic stop/TERM/KILL bounds'
    stopped=1
  elif [[ "$watchdog_pid" =~ ^[1-9][0-9]*$ ]]; then
    wait "$watchdog_pid" 2>/dev/null || true
  fi
  set -e
  (( stopped == 0 ))
}

cleanup_swap() {
  local current used mem_available required
  set +e
  [[ -d "$resource_dir" ]] && : >"${resource_dir}/swap-cleanup.log"
  if (( terminal_absence_verified != 1 || workers_remain != 0 )); then
    printf 'REFUSED: terminal server/runtime absence was not verified; swap preserved\n' \
      >>"${resource_dir}/swap-cleanup.log"
    set -e
    return 1
  fi
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
  local journal_rc runtime_rc
  mkdir -p "$resource_dir"
  cp /proc/meminfo "${resource_dir}/meminfo-final.txt" 2>/dev/null || true
  cp /proc/swaps "${resource_dir}/swaps-final.txt" 2>/dev/null || true
  df -PB1 /var/tmp >"${resource_dir}/root-filesystem-final.txt" 2>&1 || true
  systemctl is-system-running >"${resource_dir}/system-manager-final.txt" 2>&1 || true
  systemctl --user is-system-running >"${resource_dir}/user-manager-final.txt" 2>&1 || true
  systemctl show user@1000.service -p ActiveEnterTimestamp --value \
    >"${resource_dir}/user-manager-active-enter-final.txt" 2>&1 || true
  systemctl --failed --plain --no-legend \
    >"${resource_dir}/failed-system-units-final.txt" 2>&1 || true
  if timeout --signal=TERM --kill-after=5s 30s journalctl -k \
    --since "@${journal_start_epoch}" --no-pager \
    >"${resource_dir}/kernel-journal-final.log" 2>"${resource_dir}/kernel-journal-final.err"; then
    journal_rc=0
  else
    journal_rc=$?
  fi
  write_atomic "${resource_dir}/kernel-journal-final.rc" "$journal_rc"
  set +e
  scan_runtime_conflicts "${resource_dir}/runtime-conflicts-final.json"
  runtime_rc=$?
  set -e
  write_atomic "${resource_dir}/runtime-conflicts-final.rc" "$runtime_rc"
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
    terminate_owned_server_group 'outer emergency exit' || inner_stopped=0
    terminate_inner_bounded || inner_stopped=0
    if (( inner_stopped == 1 )) && [[ "$inner_pid" =~ ^[1-9][0-9]*$ ]]; then
      wait "$inner_pid" 2>/dev/null || true
    fi
    stop_watchdog || { inner_stopped=0; rc=70; }
    terminal_server_group_absent || inner_stopped=0
    if (( inner_stopped == 1 && workers_remain == 0 )); then
      cleanup_swap || rc=70
    else
      printf 'REFUSED: server workers or supervisor remain; temporary swap preserved\n' \
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

[[ $# == 0 ]] || { printf 'FAIL: attempt-11 swap supervisor takes no arguments\n' >&2; exit 2; }
[[ "$expected_attempt10_closeout" =~ ^[0-9a-f]{64}$ &&
   "$expected_attempt10_manifest" =~ ^[0-9a-f]{64}$ &&
   "$expected_attempt10_manifest_entries" =~ ^[1-9][0-9]*$ ]] || {
  printf 'FAIL: attempt-11 packet is contingent on finalized attempt-10 evidence\n' >&2
  exit 1
}
[[ "$(sha256sum "$attempt10_closeout" | cut -d' ' -f1)" == "$expected_attempt10_closeout" ]] || {
  printf 'FAIL: finalized vision attempt-10 closeout changed\n' >&2
  exit 1
}
jq -e '.status == "closed-pre-admission-host-memory-floor-after-swap-treatment" and
  .attempt == 10 and .classification.phase == "derived-inner host-memory admission" and
  .classification.temporary_swap_created_and_activated == true and
  .classification.inner_state_established == false and
  .classification.gpu_or_collective_work_started == false and
  .classification.launcher_started == false and .classification.model_load_started == false and
  .classification.client_invoked == false and
  .classification.matrix_or_site_credit == false and
  .admission_evidence.failed_gate.required_kib == 110100480 and
  .admission_evidence.failed_gate.required_gib == 105 and
  .admission_evidence.failed_gate.supervisor_output == "FAIL: less than 105 GiB host memory is available" and
  .temporary_swap_evidence.requested_bytes == 68719476736 and
  .temporary_swap_evidence.priority == -1 and
  .temporary_swap_evidence.restored_layout_exact == true and
  .temporary_swap_evidence.inactive_after == true and
  .temporary_swap_evidence.file_absent_after == true and
  .cleanup.listener_19689_after == false and
  .cleanup.model_or_worker_process_after == false and
  .cleanup.system_manager_after == "running" and .cleanup.user_manager_after == "running" and
  .cleanup.user_manager_activation_epoch_unchanged == true and
  .raw_evidence.combined_manifest_sha256 == "68470e550fcdbb667137bf5da8402647995dddc69bf06595a7b07193556b80bd" and
  .raw_evidence.combined_manifest_entries == 47 and
  .coverage_and_protected_results.site_or_matrix_changed == false and
  .coverage_and_protected_results.captured_eager_speed_changed == false and
  .coverage_and_protected_results.protected_results_changed == false' "$attempt10_closeout" >/dev/null || {
  printf 'FAIL: vision attempt-10 closeout is not the frozen administrative stop\n' >&2
  exit 1
}
[[ "$(sha256sum "$attempt10_manifest" | cut -d' ' -f1)" == "$expected_attempt10_manifest" &&
   "$(wc -l <"$attempt10_manifest")" == "$expected_attempt10_manifest_entries" ]] || {
  printf 'FAIL: finalized vision attempt-10 primary-evidence manifest changed\n' >&2
  exit 1
}
[[ "$(sha256sum "$source_supervisor" | cut -d' ' -f1)" == "$expected_source" ]] || { printf 'FAIL: attempt-11 inner supervisor source changed\n' >&2; exit 1; }
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]] || { printf 'FAIL: attempt-11 wrapper changed\n' >&2; exit 1; }
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]] || { printf 'FAIL: attempt-11 client adapter changed\n' >&2; exit 1; }
[[ "$(sha256sum "$watchdog" | cut -d' ' -f1)" == "$expected_watchdog" ]] || { printf 'FAIL: attempt-11 watchdog changed\n' >&2; exit 1; }
printf '%s  %s\n' "$expected_classifier" "$classifier" | sha256sum -c - >/dev/null || { printf 'FAIL: journal classifier hash changed\n' >&2; exit 1; }
printf '%s  %s\n' "$expected_runtime_classifier" "$runtime_classifier" | sha256sum -c - >/dev/null || { printf 'FAIL: runtime classifier hash changed\n' >&2; exit 1; }
printf '%s  %s\n' "$expected_runtime_classifier_test" "$runtime_classifier_test" | sha256sum -c - >/dev/null || { printf 'FAIL: runtime classifier fixture hash changed\n' >&2; exit 1; }
printf '%s  %s\n' "$expected_resource_policy_test" "$resource_policy_test" | sha256sum -c - >/dev/null || { printf 'FAIL: attempt-11 resource-policy fixture hash changed\n' >&2; exit 1; }
[[ "$outer_starttime" =~ ^[1-9][0-9]*$ && -f "$outer_script" && ! -L "$outer_script" ]] || { printf 'FAIL: outer supervisor process identity is invalid\n' >&2; exit 1; }
"$runtime_classifier_test" >/dev/null || { printf 'FAIL: runtime classifier fixtures failed\n' >&2; exit 1; }
"$resource_policy_test" >/dev/null || { printf 'FAIL: attempt-11 resource-policy fixtures failed\n' >&2; exit 1; }
[[ "$(systemctl is-system-running 2>/dev/null)" == running &&
   "$(systemctl is-active user@1000.service 2>/dev/null)" == active &&
   "$(systemctl --user is-system-running 2>/dev/null)" == running &&
   -z "$(systemctl --failed --plain --no-legend 2>/dev/null)" ]] || {
  printf 'FAIL: system or user manager is not stable before attempt-11 treatment\n' >&2
  exit 1
}
user_active_timestamp=$(systemctl show user@1000.service -p ActiveEnterTimestamp --value)
user_active_epoch=$(date -d "$user_active_timestamp" +%s 2>/dev/null || true)
[[ "$user_active_epoch" =~ ^[1-9][0-9]*$ ]] &&
  (( $(date +%s) - user_active_epoch >= 900 )) || {
  printf 'FAIL: user manager has not remained active for 900 recovery seconds\n' >&2
  exit 1
}
[[ -f "$sudo_password" && ! -L "$sudo_password" && -r "$sudo_password" && \
   "$(stat -c '%U:%a:%F' "$sudo_password")" == 'steve:600:regular file' ]] || { printf 'FAIL: sudo password file identity/permissions invalid\n' >&2; exit 1; }
for path in "$resource_dir" "$resource_archive_dir" "$inner_evidence" "$run_dir" "$cache_dir" "$compile_dir" "$rpc_dir" \
  "$swapfile" "${outer_state}.pid" "${outer_state}.rc" "${state}.pid" "${state}.child.pid" \
  "${outer_state}.inner.pid" "${outer_state}.watchdog.pid" "${outer_state}.watchdog.starttime" \
  "${outer_state}.deadline-epoch" \
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
cp "$attempt10_closeout" "${resource_dir}/vision-attempt10-administrative-closeout.json"
cp "$attempt10_manifest" "${resource_dir}/vision-attempt10-primary-evidence.sha256"
write_atomic "${resource_dir}/user-manager-active-enter-epoch.txt" "$user_active_epoch"
write_atomic "${resource_dir}/user-manager-active-enter-timestamp.txt" "$user_active_timestamp"
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
  -e 's#^script_dir=.*#script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools#' \
  -e 's|journalctl -k |timeout --signal=TERM --kill-after=5s 30s journalctl -k |g' \
  "$source_supervisor" >"$derived_supervisor"
chmod 0500 "$derived_supervisor"
[[ "$(sha256sum "$derived_supervisor" | cut -d' ' -f1)" == "$expected_derived" ]] || { printf 'FAIL: derived attempt-11 supervisor hash mismatch\n' >&2; exit 1; }
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
watchdog_starttime=$(awk '{print $22}' "/proc/${watchdog_pid}/stat" 2>/dev/null || true)
[[ "$watchdog_starttime" =~ ^[1-9][0-9]*$ ]] || {
  write_atomic "${state}.failed" 'FAIL vision attempt-11 resource watchdog starttime unavailable'
  exit 70
}
write_atomic "${outer_state}.watchdog.pid" "$watchdog_pid"
write_atomic "${outer_state}.watchdog.starttime" "$watchdog_starttime"
for _ in $(seq 1 100); do
  [[ -s "${resource_dir}/watchdog.heartbeat-epoch" ]] && break
  kill -0 "$watchdog_pid" 2>/dev/null || break
  sleep .1
done
heartbeat_epoch=$(cat "${resource_dir}/watchdog.heartbeat-epoch" 2>/dev/null || true)
[[ "$heartbeat_epoch" =~ ^[1-9][0-9]*$ ]] && (( $(date +%s) - heartbeat_epoch <= 10 )) || {
  write_atomic "${state}.failed" 'FAIL vision attempt-11 resource watchdog heartbeat did not start'
  exit 70
}

while kill -0 "$inner_pid" 2>/dev/null; do
  if ! validate_staged_inputs; then
    latch_resource_fault 'staged wrapper/client identity, mode, or hash changed'
    break
  fi
  if (( $(date +%s) >= outer_deadline_epoch )); then
    latch_resource_fault 'model/inner occupancy exceeded 16200 seconds'
    break
  fi
  if ! kill -0 "$watchdog_pid" 2>/dev/null; then
    [[ -e "${resource_dir}/resource.failed" ]] || \
      latch_resource_fault 'resource watchdog exited unexpectedly'
    resource_fault=1
    break
  fi
  heartbeat_epoch=$(cat "${resource_dir}/watchdog.heartbeat-epoch" 2>/dev/null || true)
  if [[ ! "$heartbeat_epoch" =~ ^[1-9][0-9]*$ ]] || (( $(date +%s) - heartbeat_epoch > 10 )); then
    latch_resource_fault 'resource watchdog heartbeat stale beyond 10 seconds'
    break
  fi
  sleep 2
done
inner_wait_timed_out=0
if kill -0 "$inner_pid" 2>/dev/null; then
  terminate_owned_server_group 'outer fault/deadline/watchdog stop' || true
  terminate_inner_bounded || inner_wait_timed_out=1
fi
if (( inner_wait_timed_out == 1 || workers_remain == 1 )); then
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
if (( inner_rc == 0 )); then
  jq -e '.status == "passed" and .text_recovery == "passed" and
    .identity.model_revision == "bcd9f01ddc9cff2316eb84281bebcd5b058bddce" and
    .identity.vllm_head == "1372c62d975c554f4b465c8299bc5f3295301ceb" and
    .identity.kernel_head == "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4" and
    .identity.stage_build_head == "2f829747503c77d4814834dffd0840fb1dd9f75a" and
    .identity.tp == 4 and .identity.ep == 4 and .identity.mtp == 0 and
    .identity.graph == "off" and .identity.max_model_len == 512 and
    .identity.language_model_only == false and
    .identity.limit_mm_per_prompt == {"image": 1, "video": 0} and
    .identity.mm_processor_cache_gb == 0 and
    .identity.mm_encoder_tp_mode == "weights" and
    .vision.observed == 9 and .vision.expected == 9 and
    .vision.all_passed == true and .health_after_final_request == "passed" and
    .speed_claim == false and .speed_credit == false and
    .deployment_credit == false and .protected_results_changed == false' \
    "${run_dir}/vision-attempt11-summary.json" >/dev/null 2>&1 || \
    latch_resource_fault 'successful inner result lacked exact bounded vision gates'
fi
stop_watchdog || resource_fault=1
terminal_server_group_absent || resource_fault=1
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
if (( inner_wait_timed_out == 0 && workers_remain == 0 )); then
  cleanup_swap || cleanup_rc=$?
else
  printf 'REFUSED: server workers or supervisor remain; temporary swap preserved\n' \
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
if [[ "$(cat "${resource_dir}/kernel-journal-final.rc" 2>/dev/null)" == 0 ]]; then
  "$classifier" "${resource_dir}/kernel-journal-final.log" \
    "${resource_dir}/root-nvme-corrected-events-final.log" || rc=70
else
  rc=70
fi
[[ "$(cat "${resource_dir}/runtime-conflicts-final.rc" 2>/dev/null)" == 0 ]] && \
  jq -e '.schema == "neural.download.q38-runtime-conflict-scan.v3" and
    .status == "clear" and (.conflicts | length) == 0 and
    (.errors | length) == 0 and .binding.supervisor.pid > 0 and
    (.vanished_races | type) == "array" and
    all(.vanished_races[]; .classification == "vanished_race" and .field == "stat") and
    (.scanned_processes | length) > 0' \
    "${resource_dir}/runtime-conflicts-final.json" >/dev/null 2>&1 || rc=70
final_user_active_timestamp=$(cat "${resource_dir}/user-manager-active-enter-final.txt" 2>/dev/null || true)
final_user_active_epoch=$(date -d "$final_user_active_timestamp" +%s 2>/dev/null || true)
[[ "$(cat "${resource_dir}/system-manager-final.txt" 2>/dev/null)" == running &&
   "$(cat "${resource_dir}/user-manager-final.txt" 2>/dev/null)" == running &&
   ! -s "${resource_dir}/failed-system-units-final.txt" &&
   "$final_user_active_epoch" == "$user_active_epoch" ]] || rc=70
write_atomic "${outer_state}.rc" "$rc"
write_atomic "${resource_dir}/inner-supervisor.rc" "$inner_rc"
write_atomic "${resource_dir}/final.rc" "$rc"
finished=1
exit "$rc"
