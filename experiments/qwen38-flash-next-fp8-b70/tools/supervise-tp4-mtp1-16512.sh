#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
wrapper="${script_dir}/launch-tp4-ep4-eager-mtp1-16512-headroom40.sh"
state=/tmp/q38-mtp1-16512-supervisor-a1
stop_file="${state}.stop"
run_parent=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
campaign=qwen38-flash-next-fp8-tp4-ep4-eager-mtp1-16512-r1
attempt=1
run_dir="${run_parent}/${campaign}-attempt${attempt}"
evidence_dir="${run_parent}/supervisor-${campaign}-attempt${attempt}"
compile_dir="/tmp/${campaign}-attempt${attempt}-compile"
rpc_dir="/tmp/${campaign}-attempt${attempt}-rpc"
cache_dir="/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/${campaign}-attempt${attempt}"
expected=7525b0c7a809a5c75a9ff9fa93661f906c9b745d5425d6fc0de9a02b5b181861
child=""
launcher=""
recorded_server_pid=""
recorded_server_pgid=""
started=0
finished=0
requested_stop=0
valid_classification=0
journal_start_epoch=$(date +%s)

write_atomic() {
  local path=$1 value=$2 tmp
  tmp="${path}.tmp.$$"
  printf '%s\n' "$value" >"$tmp"
  mv "$tmp" "$path"
}

owned_server_pid() {
  local pid command
  pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
  [[ "$pid" =~ ^[1-9][0-9]*$ && -e "/proc/${pid}" ]] || return 1
  command=$(tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null || true)
  [[ "$command" == *"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"* && \
     "$command" == *"--port 19681"* ]] || return 1
  printf '%s\n' "$pid"
}

remember_server_group() {
  local pid pgid
  pid=$(owned_server_pid 2>/dev/null || true)
  [[ -n "$pid" ]] || return 0
  pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
  [[ "$pgid" =~ ^[1-9][0-9]*$ ]] || return 0
  recorded_server_pid=$pid
  recorded_server_pgid=$pgid
  write_atomic "${state}.server.pid" "$recorded_server_pid"
  write_atomic "${state}.server.pgid" "$recorded_server_pgid"
}

cleanup_owned() {
  local pid
  set +e
  remember_server_group
  if [[ "$launcher" =~ ^[1-9][0-9]*$ ]] && kill -0 "$launcher" 2>/dev/null; then
    kill -TERM "$launcher" 2>/dev/null || true
  fi
  if [[ "$child" =~ ^[1-9][0-9]*$ ]] && kill -0 "$child" 2>/dev/null; then
    kill -TERM "$child" 2>/dev/null || true
  fi
  for _ in $(seq 1 30); do
    if { [[ -z "$child" ]] || ! kill -0 "$child" 2>/dev/null; } && \
       { [[ -z "$launcher" ]] || ! kill -0 "$launcher" 2>/dev/null; }; then
      break
    fi
    sleep 1
  done
  pid=$(owned_server_pid 2>/dev/null || true)
  if [[ -n "$pid" ]]; then
    kill -TERM -- "-${pid}" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    kill -KILL -- "-${pid}" 2>/dev/null || true
  fi
  if [[ "$child" =~ ^[1-9][0-9]*$ ]] && kill -0 "$child" 2>/dev/null; then
    kill -KILL "$child" 2>/dev/null || true
  fi
  wait "$child" 2>/dev/null || true
  find "$rpc_dir" -mindepth 1 -delete 2>/dev/null || true
  rmdir "$rpc_dir" 2>/dev/null || true
  find "$compile_dir" -mindepth 1 -delete 2>/dev/null || true
  rmdir "$compile_dir" 2>/dev/null || true
  set -e
}

capture_postflight() {
  local destination=$evidence_dir device journal_rc
  mkdir -p "$destination"
  if journalctl -k --since "@${journal_start_epoch}" --no-pager \
    >"${destination}/kernel-journal.log" 2>"${destination}/kernel-journal.err"; then
    journal_rc=0
  else
    journal_rc=$?
  fi
  write_atomic "${destination}/kernel-journal.rc" "$journal_rc"
  timeout 30s xpu-smi discovery -j >"${destination}/xpu-discovery.json" \
    2>"${destination}/xpu-discovery.err" || true
  for device in 0 1 2 3; do
    timeout 30s xpu-smi stats -d "$device" -j \
      >"${destination}/xpu-stats-${device}.json" \
      2>"${destination}/xpu-stats-${device}.err" || true
  done
  pgrep -af 'vllm|qwen38-flash-next|torch.distributed|xccl_probe' \
    >"${destination}/processes-after.txt" || true
  ss -ltnp >"${destination}/listeners-after.txt" 2>&1 || true
  cp -a "${state}.pid" "${state}.child.pid" "${state}.launcher.pid" \
    "${state}.server.pid" "${state}.server.pgid" "${state}.rc" \
    "$destination/" 2>/dev/null || true
  cp -a "$stop_file" "$destination/stop-sentinel.txt" 2>/dev/null || true
  if [[ -d "$run_dir" ]]; then
    mkdir -p "${run_dir}/supervisor-postflight"
    cp -a "${destination}/." "${run_dir}/supervisor-postflight/"
  fi
}

postflight_is_clean() {
  local device memory
  [[ ! -e "$compile_dir" && ! -e "$rpc_dir" ]] || return 1
  ! ss -ltn 2>/dev/null | grep -q ':19681 ' || return 1
  ! owned_server_pid >/dev/null 2>&1 || return 1
  [[ "$(cat "${evidence_dir}/kernel-journal.rc" 2>/dev/null)" == 0 ]] || return 1
  [[ -s "${evidence_dir}/xpu-discovery.json" ]] || return 1
  jq -e '.device_list | map([
      .device_id, .device_name, .pci_bdf_address, .drm_device
    ]) == [
      [0, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:23:00.0", "/dev/dri/card3"],
      [1, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:27:00.0", "/dev/dri/card4"],
      [2, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:43:00.0", "/dev/dri/card0"],
      [3, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:47:00.0", "/dev/dri/card2"]
    ]' "${evidence_dir}/xpu-discovery.json" >/dev/null || return 1
  for device in 0 1 2 3; do
    [[ -s "${evidence_dir}/xpu-stats-${device}.json" ]] || return 1
    memory=$(jq -er 'first(.device_level[] |
      select(.metrics_type == "XPUM_STATS_MEMORY_USED") | .value) |
      select(type == "number")' "${evidence_dir}/xpu-stats-${device}.json") || return 1
    awk -v value="$memory" 'BEGIN { exit !(value < 256) }' || return 1
  done
  if [[ "$recorded_server_pgid" =~ ^[1-9][0-9]*$ ]]; then
    ! pgrep -g "$recorded_server_pgid" >/dev/null 2>&1 || return 1
  elif (( requested_stop == 1 )); then
    return 1
  fi
  ! grep -Eqi 'xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
    "${evidence_dir}/kernel-journal.log" || return 1
}

classification_is_valid() {
  local line status
  [[ -f "${run_dir}/request1-classified.txt" && \
     "$(wc -l < "${run_dir}/request1-classified.txt")" == 1 ]] || return 1
  line=$(cat "${run_dir}/request1-classified.txt")
  status=$(jq -r '.status' "${run_dir}/request1-adjudication.json" 2>/dev/null) || return 1
  if [[ "$status" == 'quarantined-generic-exact-depth-parity-match' ]]; then
    [[ "$line" == 'QUARANTINE generic exact-16K MTP1 counters and same-runtime MTP0 parity pass; semantic and repeat gates absent' ]] || return 1
  elif [[ "$status" == 'quarantined-generic-exact-depth-parity-mismatch' ]]; then
    [[ "$line" == 'QUARANTINE generic exact-16K MTP1 counters pass; same-runtime MTP0 parity differs; semantic and repeat gates absent' ]] || return 1
  else
    return 1
  fi
  jq -e '.generic_exact_depth_gate == "passed" and
    .mtp_counter_gate == "passed" and
    .prompt_tokens == 16384 and .completion_tokens == 128 and
    .cached_tokens == 0 and .speed_credit == false and .quality_credit == false and
    .deployment_credit == false and .matrix_classification == "grade-d-quarantined-capability" and
    .repeat_gate == "absent" and
    .semantic_gate == "absent"' \
    "${run_dir}/request1-adjudication.json" >/dev/null 2>&1
}

emergency_exit() {
  local rc=$?
  (( rc != 0 )) || rc=70
  if (( started == 1 && finished == 0 )); then
    cleanup_owned
    write_atomic "${state}.rc" "$rc"
    capture_postflight
  fi
}
trap emergency_exit EXIT
trap 'exit 130' INT TERM HUP

[[ $# == 0 ]] || { printf 'FAIL: supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected" ]] || {
  printf 'FAIL: frozen launcher hash mismatch\n' >&2
  exit 1
}
for path in "${state}.pid" "${state}.child.pid" "${state}.launcher.pid" \
  "${state}.server.pid" "${state}.server.pgid" "${state}.rc" "$stop_file"; do
  [[ ! -e "$path" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$path" >&2; exit 1; }
done
[[ ! -e "$run_dir" && ! -e "$evidence_dir" && ! -e "$cache_dir" && \
   ! -e "$compile_dir" && ! -e "$rpc_dir" ]] || {
  printf 'FAIL: refusing to reuse frozen MTP1/16K paths\n' >&2
  exit 1
}

mkdir -p "$evidence_dir"
write_atomic "${evidence_dir}/journal-start-epoch.txt" "$journal_start_epoch"
write_atomic "${state}.pid" "$$"
started=1
set +e
timeout --signal=TERM --kill-after=30s 3600s \
  env -i \
    HOME=/home/steve \
    USER=steve \
    LOGNAME=steve \
    LANG=C.UTF-8 \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  "$wrapper" --execute --ack 'RUN qwen38-flash-next-fp8-tp4-ep4-eager-mtp1-16512-r1' &
child=$!
write_atomic "${state}.child.pid" "$child"
launcher=""
for _ in $(seq 1 50); do
  mapfile -t descendants < <(pgrep -P "$child" || true)
  if [[ "${#descendants[@]}" == 1 ]]; then
    launcher=${descendants[0]}
    break
  fi
  kill -0 "$child" 2>/dev/null || break
  sleep .2
done
if [[ -z "$launcher" ]]; then
  printf 'FAIL: bounded launcher descendant was not uniquely identified\n' >&2
  cleanup_owned
  write_atomic "${state}.rc" 70
  capture_postflight
  finished=1
  exit 70
fi
write_atomic "${state}.launcher.pid" "$launcher"

while kill -0 "$child" 2>/dev/null; do
  remember_server_group
  if [[ -e "$stop_file" ]]; then
    if [[ "$(wc -l < "$stop_file")" == 1 ]] &&
       grep -Fxq 'STOP after completed MTP1 active-16K classification' "$stop_file" &&
       classification_is_valid; then
      valid_classification=1
    elif [[ "$(wc -l < "$stop_file")" == 1 ]] &&
         grep -Fxq 'STOP after failed MTP1 active-16K request' "$stop_file"; then
      valid_classification=0
    else
      printf 'FAIL: invalid stop sentinel or incomplete classification\n' >&2
    fi
    requested_stop=1
    kill -TERM "$launcher" 2>/dev/null || true
    break
  fi
  sleep 2
done
wait "$child"
child_rc=$?
set -e

cleanup_owned
if (( requested_stop == 1 && valid_classification == 1 )); then
  rc=0
else
  rc=$child_rc
  (( rc != 0 )) || rc=70
fi
write_atomic "${state}.rc" "$rc"
capture_postflight
if ! postflight_is_clean; then
  printf 'FAIL: MTP1/16K postflight was not clean\n' >&2
  rc=70
  write_atomic "${state}.rc" "$rc"
  capture_postflight
fi
finished=1
exit "$rc"
