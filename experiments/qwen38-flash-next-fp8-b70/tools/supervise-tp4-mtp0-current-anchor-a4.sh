#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
wrapper="${script_dir}/launch-tp4-mtp0-current-anchor-a4.sh"
expected_wrapper=adb0b7dc7a0f2aa21a4d2dd217a3107a579c42a921e1139bc1eda8801d46219d
client="${script_dir}/run-tp4-mtp0-current-anchor-a4-client.sh"
expected_client=28957596b743e068c50c65ceaa716bb79a47908167ab7ac3ec4fb629346135e0
state=/tmp/q38-mtp0-current-anchor-a4
stop_file="${state}.stop"
failure_file="${state}.failed"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4
cache_dir=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4
compile_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4-compile
rpc_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4-rpc
evidence_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4-supervisor
port=19673
child=""
launcher=""
server_pid=""
server_pgid=""
started=0
finished=0
journal_start_epoch=$(date +%s)
deadline_epoch=$((journal_start_epoch + 10000))

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
     "$command" == *"--port ${port}"* && "$command" == *"--max-model-len 4352"* ]] || return 1
  printf '%s\n' "$pid"
}

remember_server() {
  local pid pgid raw_pid
  raw_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
  if [[ ! "$raw_pid" =~ ^[1-9][0-9]*$ || ! -e "/proc/${raw_pid}" ]]; then
    return 0
  fi
  pid=$(owned_server_pid 2>/dev/null || true)
  [[ -n "$pid" ]] || return 1
  pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
  [[ "$pgid" =~ ^[1-9][0-9]*$ ]] || return 1
  server_pid=$pid
  server_pgid=$pgid
  write_atomic "${state}.server.pid" "$server_pid"
  write_atomic "${state}.server.pgid" "$server_pgid"
}

cleanup_owned() {
  set +e
  remember_server || true
  if [[ "$launcher" =~ ^[1-9][0-9]*$ ]] && kill -0 "$launcher" 2>/dev/null; then
    kill -TERM "$launcher" 2>/dev/null || true
  fi
  if [[ "$child" =~ ^[1-9][0-9]*$ ]] && kill -0 "$child" 2>/dev/null; then
    kill -TERM "$child" 2>/dev/null || true
  fi
  for _ in $(seq 1 30); do
    { [[ -z "$child" ]] || ! kill -0 "$child" 2>/dev/null; } && break
    sleep 1
  done
  if [[ "$server_pgid" =~ ^[1-9][0-9]*$ ]] && pgrep -g "$server_pgid" >/dev/null 2>&1; then
    kill -TERM -- "-${server_pgid}" 2>/dev/null || true
    for _ in $(seq 1 20); do
      pgrep -g "$server_pgid" >/dev/null 2>&1 || break
      sleep 1
    done
    kill -KILL -- "-${server_pgid}" 2>/dev/null || true
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
  local device journal_rc
  mkdir -p "$evidence_dir"
  if journalctl -k --since "@${journal_start_epoch}" --no-pager \
    >"${evidence_dir}/kernel-journal.log" 2>"${evidence_dir}/kernel-journal.err"; then
    journal_rc=0
  else
    journal_rc=$?
  fi
  write_atomic "${evidence_dir}/kernel-journal.rc" "$journal_rc"
  timeout 30s xpu-smi discovery -j >"${evidence_dir}/xpu-discovery.json" \
    2>"${evidence_dir}/xpu-discovery.err" || true
  for device in 0 1 2 3; do
    timeout 30s xpu-smi stats -d "$device" -j \
      >"${evidence_dir}/xpu-stats-${device}.json" \
      2>"${evidence_dir}/xpu-stats-${device}.err" || true
  done
  pgrep -af 'vllm|qwen38-flash-next|torch.distributed|xccl_probe' \
    >"${evidence_dir}/processes-after.txt" || true
  ss -ltnp >"${evidence_dir}/listeners-after.txt" 2>&1 || true
  cp -a "${state}."* "$evidence_dir/" 2>/dev/null || true
}

postflight_clean() {
  local device memory
  [[ ! -e "$compile_dir" && ! -e "$rpc_dir" ]] || return 1
  ! ss -ltn 2>/dev/null | grep -q ":${port} " || return 1
  [[ -z "$launcher" ]] || ! kill -0 "$launcher" 2>/dev/null || return 1
  [[ "$(cat "${evidence_dir}/kernel-journal.rc" 2>/dev/null)" == 0 ]] || return 1
  if [[ "$server_pgid" =~ ^[1-9][0-9]*$ ]]; then
    ! pgrep -g "$server_pgid" >/dev/null 2>&1 || return 1
  fi
  jq -e '.device_list | map([
      .device_id, .device_name, .pci_bdf_address, .drm_device
    ]) == [
      [0, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:23:00.0", "/dev/dri/card3"],
      [1, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:27:00.0", "/dev/dri/card4"],
      [2, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:43:00.0", "/dev/dri/card0"],
      [3, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:47:00.0", "/dev/dri/card2"]
    ]' "${evidence_dir}/xpu-discovery.json" >/dev/null || return 1
  for device in 0 1 2 3; do
    memory=$(jq -er 'first(.device_level[] | select(.metrics_type == "XPUM_STATS_MEMORY_USED") | .value)' \
      "${evidence_dir}/xpu-stats-${device}.json") || return 1
    awk -v value="$memory" 'BEGIN { exit !(value < 256) }' || return 1
  done
  ! grep -Eqi 'xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
    "${evidence_dir}/kernel-journal.log" || return 1
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
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]] || {
  printf 'FAIL: frozen current-anchor wrapper hash changed\n' >&2
  exit 1
}
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]] || {
  printf 'FAIL: frozen current-anchor client hash changed\n' >&2
  exit 1
}
for path in "${state}.pid" "${state}.child.pid" "${state}.launcher.pid" \
  "${state}.server.pid" "${state}.server.pgid" "${state}.rc" "$stop_file" \
  "$failure_file" "${state}.deadline-epoch" "$run_dir" "$cache_dir" "$compile_dir" "$rpc_dir" "$evidence_dir"; do
  [[ ! -e "$path" ]] || { printf 'FAIL: refusing to reuse %s\n' "$path" >&2; exit 1; }
done

mkdir -p "$evidence_dir"
write_atomic "${evidence_dir}/journal-start-epoch.txt" "$journal_start_epoch"
write_atomic "${state}.deadline-epoch" "$deadline_epoch"
write_atomic "${state}.pid" "$$"
started=1
set +e
timeout --signal=TERM --kill-after=30s 10000s env -i \
  HOME=/home/steve USER=steve LOGNAME=steve LANG=C.UTF-8 \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  "$wrapper" --execute --ack 'RUN qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1' &
child=$!
set -e
write_atomic "${state}.child.pid" "$child"
for _ in $(seq 1 50); do
  mapfile -t descendants < <(pgrep -P "$child" || true)
  if [[ "${#descendants[@]}" == 1 ]]; then
    launcher=${descendants[0]}
    break
  fi
  kill -0 "$child" 2>/dev/null || break
  sleep .2
done
[[ "$launcher" =~ ^[1-9][0-9]*$ ]] || {
  printf 'FAIL: launcher descendant was not uniquely identified\n' >&2
  exit 70
}
write_atomic "${state}.launcher.pid" "$launcher"

requested_stop=0
valid_stop=0
while kill -0 "$child" 2>/dev/null; do
  remember_server || { printf 'FAIL: owned server identity changed\n' >&2; exit 70; }
  if [[ -e "$stop_file" || -e "$failure_file" ]]; then
    requested_stop=1
    if [[ -e "$stop_file" ]] && \
       [[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]] && \
       grep -Fxq 'STOP after passed current-runtime MTP0 anchor' "$stop_file" && \
       grep -Fxq 'PASS recovery quality short-repeat exact-4K-repeat current-runtime MTP0 anchor' \
         "${run_dir}/client-gates-passed.txt" 2>/dev/null && \
       jq -e '.status == "passed" and .recovery_canary == "passed" and
         .identity.model_revision == "bcd9f01ddc9cff2316eb84281bebcd5b058bddce" and
         .identity.vllm_head == "1372c62d975c554f4b465c8299bc5f3295301ceb" and
         .identity.kernel_head == "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4" and
         .identity.stage_build_head == "2f829747503c77d4814834dffd0840fb1dd9f75a" and
         .identity.tp == 4 and .identity.ep == 4 and .identity.mtp == 0 and
         .identity.graph == "off" and .identity.max_model_len == 4352 and
         .exact_4k.repeats == 2 and .exact_4k.same_boot_output_repeat == true and
         .exact_4k.cached_tokens == [0, 0] and .protected_results_changed == false' \
         "${run_dir}/current-anchor-summary.json" >/dev/null 2>&1; then
      valid_stop=1
    fi
    kill -TERM "$launcher" 2>/dev/null || true
    break
  fi
  sleep 2
done
set +e
wait "$child"
child_rc=$?
set -e
cleanup_owned
rc=$child_rc
if (( requested_stop == 1 && valid_stop == 1 )); then rc=0; fi
(( rc != 0 )) || (( valid_stop == 1 )) || rc=70
write_atomic "${state}.rc" "$rc"
capture_postflight
if ! postflight_clean; then
  printf 'FAIL: current-anchor postflight was not clean\n' >&2
  rc=70
  write_atomic "${state}.rc" "$rc"
fi
write_atomic "${evidence_dir}/final.rc" "$rc"
finished=1
exit "$rc"
