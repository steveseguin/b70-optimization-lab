#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
watchdog="${script_dir}/watch-tp4-mtp0-current-piecewise-graph-a6-resources.sh"
supervisor="${script_dir}/supervise-tp4-mtp0-current-piecewise-graph-a6-swap64.sh"
wrapper="${script_dir}/launch-tp4-mtp0-current-piecewise-graph-a6.sh"
client="${script_dir}/run-tp4-mtp0-current-piecewise-graph-a6-client.sh"
a5_server_log=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt5/server.log
a5_resource_log=/var/tmp/q38-piecewise-graph-a5-resource/resource-watchdog.tsv

phase_decision() {
  local phase=$1 previous=$2 current=$3 drop=0
  (( previous > current )) && drop=$((previous - current))
  if (( phase == 1 && current < 31457280 )); then
    printf 'floor\n'
  elif (( phase == 1 && current < 41943040 && drop >= 8388608 )); then
    printf 'drop\n'
  else
    printf 'pass\n'
  fi
}

signature_decision() {
  grep -Eqi '\[TTM\].*Buffer eviction failed|page allocation failure|invoked oom-killer|oom-kill:|Out of memory: Killed process|Memory cgroup out of memory' \
    && printf 'stop\n' || printf 'pass\n'
}

cleanup_decision() {
  local absence_verified=$1 workers_remain=$2
  (( absence_verified == 1 && workers_remain == 0 )) && printf 'cleanup\n' || printf 'preserve\n'
}

monotonic_seconds() {
  awk '{print int($1)}' /proc/uptime
}

[[ "$(phase_decision 0 50331648 30408704)" == pass ]]
[[ "$(phase_decision 1 33554432 30408704)" == floor ]]
[[ "$(phase_decision 1 50331648 40894464)" == drop ]]
[[ "$(phase_decision 1 48234496 40894464)" == pass ]]
[[ "$(phase_decision 1 62914560 42991616)" == pass ]]

[[ "$(printf '%s\n' 'kernel: [TTM] Buffer eviction failed' | signature_decision)" == stop ]]
[[ "$(printf '%s\n' 'kernel: VLLM::Worker_TP: page allocation failure: order:0' | signature_decision)" == stop ]]
[[ "$(printf '%s\n' 'kernel: invoked oom-killer: gfp_mask=0x0' | signature_decision)" == stop ]]
[[ "$(printf '%s\n' 'kernel: harmless corrected root-port receiver event' | signature_decision)" == pass ]]

[[ -f "$a5_server_log" && -f "$a5_resource_log" ]]
a5_loaded_rank_count=$({ grep -aoE 'Worker_TP[0-3]_EP[0-3].*Model loading took' "$a5_server_log" || true; } | \
  sed -E 's/.*Worker_TP([0-3])_EP([0-3]).*/\1:\2/' | sort -u | wc -l)
[[ "$a5_loaded_rank_count" == 4 ]]
grep -aEq 'Dynamo bytecode transform time:|Cache the graph of compile range|Capturing CUDA graphs \(mixed prefill-decode, PIECEWISE\)' \
  "$a5_server_log"
awk -F '\t' 'NR > 1 && $2 < 12582912 {found=1} END {exit !found}' "$a5_resource_log"

[[ "$(cleanup_decision 0 0)" == preserve ]]
[[ "$(cleanup_decision 1 1)" == preserve ]]
[[ "$(cleanup_decision 1 0)" == cleanup ]]

# A deliberately nonresponsive stand-in proves the fixture itself cannot hang:
# TERM gets one monotonic second, KILL follows, and the process must disappear.
bash -c 'trap "" TERM; while :; do :; done' &
hung_pid=$!
sleep .1
hung_start=$(monotonic_seconds)
kill -TERM "$hung_pid"
hung_deadline=$((hung_start + 1))
while kill -0 "$hung_pid" 2>/dev/null && (( $(monotonic_seconds) < hung_deadline )); do
  sleep .05
done
kill -KILL "$hung_pid" 2>/dev/null || true
set +e
wait "$hung_pid" 2>/dev/null
set -e
(( $(monotonic_seconds) - hung_start <= 3 ))
! kill -0 "$hung_pid" 2>/dev/null

grep -Fq 'loaded_rank_count == 4 || compile_marker == 1' "$watchdog"
grep -Fq 'phase_mem_floor_kib=31457280' "$watchdog"
grep -Fq 'phase_drop_floor_kib=41943040' "$watchdog"
grep -Fq 'phase_drop_limit_kib=8388608' "$watchdog"
grep -Fq 'kill -TERM -- "-${server_group}"' "$supervisor"
grep -Fq 'kill -KILL -- "-${server_group}"' "$supervisor"
grep -Fq "awk '{print int(\$1)}' /proc/uptime" "$supervisor"
grep -Fq 'server workers or supervisor remain; temporary swap preserved' "$supervisor"
grep -Fq 'terminal_absence_verified != 1 || workers_remain != 0' "$supervisor"
grep -Fq 'wait_pid_monotonic "$watchdog_pid" 5' "$supervisor"
grep -Fq 'wait_pid_monotonic "$watchdog_pid" 3' "$supervisor"
grep -Fq 'kill -KILL "$watchdog_pid"' "$supervisor"
grep -Fq 'validate_watchdog_identity()' "$supervisor"
grep -Fq '"$current_starttime" == "$watchdog_starttime"' "$supervisor"
grep -Fq '"$command" == *"$watchdog"*' "$supervisor"
grep -Fq 'resource watchdog PID/starttime/command identity changed; refusing signal' "$supervisor"
grep -Fq '"${outer_state}.watchdog.starttime"' "$supervisor"
grep -Fq 'timeout --signal=TERM --kill-after=5s 20s journalctl' "$watchdog"
grep -Fq 'timeout --signal=TERM --kill-after=5s 30s journalctl' "$supervisor"
grep -Fq 'timeout --signal=TERM --kill-after=5s 30s journalctl -k' "$wrapper"
grep -Fq "s|^journalctl -k |timeout --signal=TERM --kill-after=5s 30s journalctl -k |" "$client"

printf 'PASS attempt-6 phase/resource/process-group policy fixtures\n'
