#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
wrapper="${script_dir}/launch-tp4-mtp0-current-vision-a2.sh"
expected_wrapper=f85720f0e12111febdbb290f97d50a1f3c1d24a0571b40f8712fee46a6f8b8c2
client="${script_dir}/run-tp4-mtp0-current-vision-a2-client.sh"
expected_client=7a41ca301cb3ee315cd83e0a25fe7befb3ba2838c17f3a5520bc89424f7e46dd
graph5_result="${script_dir}/../data/20260828-tp4-mtp0-current-piecewise-graph-attempt5-result.json"
expected_graph5_result=914ae4daf12f3dd19ced44eb1abfc15d6dd45c2b5a4f4c2db43f85fb7d1f98d9
graph5_manifest="${script_dir}/../data/20260828-tp4-mtp0-current-piecewise-graph-attempt5-primary-evidence.sha256"
expected_graph5_manifest=b2ddc4323c2b76da507736495fa81f2968bce29b5ba75bf7b5ce66d23622de4f
health_helper=/home/steve/llm-optimizations/scripts/check-qwen36-xpu-xccl-health.sh
expected_health_helper=b15dd4c248d8c4d7035c2d180b9ecc5354b1b20bdabb0c47c540b5003a1cfb78
xccl_probe=/home/steve/llm-optimizations/tools/xccl_probe.py
expected_xccl_probe=6ecd340651a6780fdbe0bd57d346540efe168bf2e3175d54e10dd8660ed5b30a
state=/tmp/q38-mtp0-current-vision-a2
stop_file="${state}.stop"
failure_file="${state}.failed"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt2
cache_dir=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt2
compile_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt2-compile
rpc_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt2-rpc
evidence_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt2-supervisor
port=19677
child=""
launcher=""
server_pid=""
server_pgid=""
started=0
finished=0
journal_start_epoch=$(date +%s)
deadline_epoch=$((journal_start_epoch + 15000))

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
     "$command" == *"--port ${port}"* && "$command" == *"--max-model-len 512"* && \
     "$command" == *"--limit-mm-per-prompt"* && \
     "$command" == *"--mm-processor-cache-gb 0"* && \
     "$command" == *"--mm-encoder-tp-mode weights"* && \
     "$command" != *"--language-model-only"* ]] || return 1
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
  cp /proc/meminfo "${evidence_dir}/meminfo-after.txt" 2>/dev/null || true
  cp /proc/swaps "${evidence_dir}/swaps-after.txt" 2>/dev/null || true
  cat /proc/pressure/memory >"${evidence_dir}/memory-pressure-after.txt" 2>/dev/null || true
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
  ! grep -Eqi 'invoked oom-killer|Out of memory: Killed process|oom-kill:|RxErr|xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
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
  printf 'FAIL: frozen vision wrapper hash changed\n' >&2
  exit 1
}
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]] || {
  printf 'FAIL: frozen vision client hash changed\n' >&2
  exit 1
}
[[ "$(sha256sum "$graph5_result" | cut -d' ' -f1)" == "$expected_graph5_result" ]] || {
  printf 'FAIL: graph attempt-5 recovery source changed\n' >&2
  exit 1
}
[[ "$(sha256sum "$graph5_manifest" | cut -d' ' -f1)" == "$expected_graph5_manifest" ]] || {
  printf 'FAIL: graph attempt-5 evidence manifest changed\n' >&2
  exit 1
}
jq -e '.status == "failed-incomplete-host-oom-during-post-load-graph-compilation" and
  .classification.healthy_api == false and .classification.client_invoked == false and
  .classification.speed_rows == 0 and .classification.matrix_or_site_credit == false and
  .cleanup.temporary_swapoff_succeeded == true and
  .cleanup.original_swap_layout_restored_exactly == true and
  .cleanup.model_or_worker_process_after == false and
  .cleanup.compile_path_after == false and .cleanup.rpc_path_after == false' \
  "$graph5_result" >/dev/null || {
  printf 'FAIL: graph attempt-5 recovery receipt is not the frozen clean closeout\n' >&2
  exit 1
}
[[ "$(sha256sum "$health_helper" | cut -d' ' -f1)" == "$expected_health_helper" &&
   "$(sha256sum "$xccl_probe" | cut -d' ' -f1)" == "$expected_xccl_probe" ]] || {
  printf 'FAIL: recovery health helper identity changed\n' >&2
  exit 1
}
[[ "$(systemctl is-system-running 2>/dev/null)" == running ]] || {
  printf 'FAIL: system manager is not running cleanly after the prior OOM\n' >&2
  exit 1
}
[[ "$(systemctl is-active user@1000.service 2>/dev/null)" == active ]] || {
  printf 'FAIL: user manager is not active after the prior OOM\n' >&2
  exit 1
}
[[ "$(systemctl --user is-system-running 2>/dev/null)" == running ]] || {
  printf 'FAIL: user manager is not running cleanly after the prior OOM\n' >&2
  exit 1
}
[[ -z "$(systemctl --failed --plain --no-legend 2>/dev/null)" ]] || {
  printf 'FAIL: failed system units remain after the prior OOM\n' >&2
  exit 1
}
user_active_timestamp=$(systemctl show user@1000.service -p ActiveEnterTimestamp --value)
user_active_epoch=$(date -d "$user_active_timestamp" +%s 2>/dev/null || true)
[[ "$user_active_epoch" =~ ^[1-9][0-9]*$ ]] || {
  printf 'FAIL: user-manager recovery age is unavailable\n' >&2
  exit 1
}
(( $(date +%s) - user_active_epoch >= 900 )) || {
  printf 'FAIL: user manager has not remained active for 900 recovery seconds\n' >&2
  exit 1
}
mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
swap_free_kib=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
root_available_bytes=$(df --output=avail -B1 / | tail -1)
external_available_bytes=$(df --output=avail -B1 /mnt/usb-models | tail -1)
shm_available_bytes=$(df --output=avail -B1 /dev/shm | tail -1)
(( mem_available_kib >= 110 * 1024 * 1024 )) || {
  printf 'FAIL: less than 110 GiB host memory is available\n' >&2
  exit 1
}
(( swap_free_kib >= 6 * 1024 * 1024 )) || {
  printf 'FAIL: less than 6 GiB swap is free\n' >&2
  exit 1
}
(( root_available_bytes >= 80 * 1024 * 1024 * 1024 )) || {
  printf 'FAIL: less than 80 GiB root space is available\n' >&2
  exit 1
}
(( external_available_bytes >= 300 * 1024 * 1024 * 1024 )) || {
  printf 'FAIL: less than 300 GiB external evidence space is available\n' >&2
  exit 1
}
(( shm_available_bytes >= 32 * 1024 * 1024 * 1024 )) || {
  printf 'FAIL: less than 32 GiB shared-memory space is available\n' >&2
  exit 1
}
for path in "${state}.pid" "${state}.child.pid" "${state}.launcher.pid" \
  "${state}.server.pid" "${state}.server.pgid" "${state}.rc" "$stop_file" \
  "$failure_file" "${state}.deadline-epoch" "$run_dir" "$cache_dir" "$compile_dir" "$rpc_dir" "$evidence_dir"; do
  [[ ! -e "$path" ]] || { printf 'FAIL: refusing to reuse %s\n' "$path" >&2; exit 1; }
done

mkdir -p "$evidence_dir"
write_atomic "${evidence_dir}/journal-start-epoch.txt" "$journal_start_epoch"
write_atomic "${evidence_dir}/recovery-window-seconds.txt" 900
write_atomic "${evidence_dir}/user-manager-active-enter-timestamp.txt" "$user_active_timestamp"
write_atomic "${evidence_dir}/user-manager-active-enter-epoch.txt" "$user_active_epoch"
systemctl is-system-running >"${evidence_dir}/system-manager-state.txt"
systemctl --user is-system-running >"${evidence_dir}/user-manager-state.txt"
systemctl --failed --plain --no-legend >"${evidence_dir}/failed-system-units.txt"
cp "$graph5_result" "${evidence_dir}/graph-attempt5-result.json"
cp "$graph5_manifest" "${evidence_dir}/graph-attempt5-primary-evidence.sha256"
cp /proc/meminfo "${evidence_dir}/meminfo-before.txt"
cp /proc/swaps "${evidence_dir}/swaps-before.txt"
cat /proc/pressure/memory >"${evidence_dir}/memory-pressure-before.txt"
df -B1 / /mnt/usb-models /dev/shm >"${evidence_dir}/filesystem-space-before.txt"
journalctl -k --since '15 minutes ago' --no-pager \
  >"${evidence_dir}/recovery-kernel-journal.log" \
  2>"${evidence_dir}/recovery-kernel-journal.err"
! grep -Eqi 'invoked oom-killer|Out of memory: Killed process|oom-kill:|RxErr|xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
  "${evidence_dir}/recovery-kernel-journal.log" || {
  printf 'FAIL: the 15-minute recovery journal is not quiet\n' >&2
  exit 1
}
! pgrep -x rsync >/dev/null && ! pgrep -x tar >/dev/null &&
  ! pgrep -x zstd >/dev/null && ! pgrep -x gzip >/dev/null || {
  printf 'FAIL: evidence archival is still active\n' >&2
  exit 1
}
! pgrep -af 'vllm|qwen38-flash-next|torch.distributed|xccl_probe' \
  >"${evidence_dir}/processes-before.txt" || {
  printf 'FAIL: model, worker, or collective process is already active\n' >&2
  exit 1
}
! ss -ltn 2>/dev/null | grep -q ":${port} " || {
  printf 'FAIL: vision attempt-2 port is already in use\n' >&2
  exit 1
}
timeout 30s xpu-smi discovery -j >"${evidence_dir}/xpu-discovery-before.json" \
  2>"${evidence_dir}/xpu-discovery-before.err"
jq -e '.device_list | map([
    .device_id, .device_name, .pci_bdf_address, .drm_device
  ]) == [
    [0, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:23:00.0", "/dev/dri/card3"],
    [1, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:27:00.0", "/dev/dri/card4"],
    [2, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:43:00.0", "/dev/dri/card0"],
    [3, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:47:00.0", "/dev/dri/card2"]
  ]' "${evidence_dir}/xpu-discovery-before.json" >/dev/null || {
  printf 'FAIL: preflight card identity changed\n' >&2
  exit 1
}
for device in 0 1 2 3; do
  timeout 30s xpu-smi stats -d "$device" -j \
    >"${evidence_dir}/xpu-stats-${device}-before.json" \
    2>"${evidence_dir}/xpu-stats-${device}-before.err"
  memory=$(jq -er 'first(.device_level[] | select(.metrics_type == "XPUM_STATS_MEMORY_USED") | .value)' \
    "${evidence_dir}/xpu-stats-${device}-before.json")
  awk -v value="$memory" 'BEGIN { exit !(value < 256) }' || {
    printf 'FAIL: card %s is not idle before recovery health\n' "$device" >&2
    exit 1
  }
done
timeout --signal=TERM --kill-after=10s 300s env \
  ROOT=/home/steve/llm-optimizations \
  PYTHON=/home/steve/.venvs/vllm-xpu/bin/python \
  PHYSICAL_DEVICES=0,1,2,3 XCCL_DEVICES=0,1,2,3 XCCL_NPROC=4 TIMEOUT_S=120 \
  FI_TCP_IFACE=lo CCL_KVS_IFACE=lo \
  "$health_helper" >"${evidence_dir}/admission-xpu-xccl-health.log" 2>&1
[[ "$(grep -Ec '^ok 2097152\.0$' "${evidence_dir}/admission-xpu-xccl-health.log")" == 4 ]] || {
  printf 'FAIL: not all four single-card recovery checks passed\n' >&2
  exit 1
}
for rank in 0 1 2 3; do
  grep -Fxq "rank ${rank} allreduce ok 4.0" \
    "${evidence_dir}/admission-xpu-xccl-health.log" || {
    printf 'FAIL: rank %s recovery collective receipt is absent\n' "$rank" >&2
    exit 1
  }
done
(
  cd "$evidence_dir"
  sha256sum admission-xpu-xccl-health.log failed-system-units.txt \
    filesystem-space-before.txt graph-attempt5-primary-evidence.sha256 \
    graph-attempt5-result.json meminfo-before.txt memory-pressure-before.txt \
    recovery-kernel-journal.log recovery-window-seconds.txt swaps-before.txt \
    system-manager-state.txt user-manager-active-enter-epoch.txt \
    user-manager-active-enter-timestamp.txt user-manager-state.txt \
    xpu-discovery-before.json xpu-stats-{0,1,2,3}-before.json \
    >admission-recovery.sha256
)
printf 'epoch\tmem_available_kib\tswap_free_kib\tpswpin\tpswpout\n' \
  >"${evidence_dir}/resource-watch.tsv"
write_atomic "${state}.deadline-epoch" "$deadline_epoch"
write_atomic "${state}.pid" "$$"
started=1
set +e
timeout --signal=TERM --kill-after=30s 15000s env -i \
  HOME=/home/steve USER=steve LOGNAME=steve LANG=C.UTF-8 \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  "$wrapper" --execute --ack 'RUN qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1' &
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
  mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
  swap_free_kib=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
  pswpin=$(awk '$1 == "pswpin" {print $2}' /proc/vmstat)
  pswpout=$(awk '$1 == "pswpout" {print $2}' /proc/vmstat)
  printf '%s\t%s\t%s\t%s\t%s\n' "$(date +%s)" "$mem_available_kib" \
    "$swap_free_kib" "$pswpin" "$pswpout" >>"${evidence_dir}/resource-watch.tsv"
  if (( mem_available_kib < 10 * 1024 * 1024 || swap_free_kib < 5 * 1024 * 1024 )); then
    write_atomic "$failure_file" \
      "FAIL vision resource floor MemAvailable=${mem_available_kib}KiB SwapFree=${swap_free_kib}KiB"
  fi
  if [[ -e "$stop_file" || -e "$failure_file" ]]; then
    requested_stop=1
    if [[ -e "$stop_file" && ! -e "$failure_file" ]] && \
       [[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]] && \
       grep -Fxq 'STOP after passed bounded vision attempt-2 client' "$stop_file" && \
       grep -Fxq 'PASS same-boot text recovery seven semantics nine fixed-vision requests health no-speed' \
         "${run_dir}/client-gates-passed.txt" 2>/dev/null && \
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
         "${run_dir}/vision-attempt2-summary.json" >/dev/null 2>&1; then
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
  printf 'FAIL: vision attempt-2 postflight was not clean\n' >&2
  rc=70
  write_atomic "${state}.rc" "$rc"
fi
write_atomic "${evidence_dir}/final.rc" "$rc"
finished=1
exit "$rc"
