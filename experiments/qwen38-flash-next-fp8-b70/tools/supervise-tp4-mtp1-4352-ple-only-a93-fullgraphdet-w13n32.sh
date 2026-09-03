#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools
wrapper="${script_dir}/launch-tp4-mtp1-4352-ple-only-a93-fullgraphdet-w13n32.sh"
expected_wrapper=2f38e1121584f266701c3e4826e4887174509535aa8dc67caddd7ae72ba27a8d
client="${script_dir}/run-tp4-mtp1-4352-ple-only-a93-fullgraphdet-w13n32-client.sh"
expected_client=02950ffbeadecb05e5212701cb66c4a9e1511c76b00b03cd5c11a156733acf86
state=/tmp/q38-mtp1-ple-only-a93
stop_file="${state}.stop"
failure_file="${state}.failed"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-exact-recurrent-4352-ple-only-r1-attempt93
cache_dir=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-exact-recurrent-4352-ple-only-r1-attempt93
compile_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-exact-recurrent-4352-ple-only-r1-attempt93-compile
rpc_dir=/tmp/q38-ple2k-a93-rpc
evidence_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-exact-recurrent-4352-ple-only-r1-attempt93-supervisor
port=19765
pressure_log="${evidence_dir}/host-pressure.tsv"
expected_nvme_aer_cor=${Q38_A93_NVME_AER_BASELINE:-}
expected_root_aer_cor=${Q38_A93_ROOT_AER_BASELINE:-}
expected_nvme_sectors_read=${Q38_A93_NVME_SECTORS_READ_BASELINE:-}
max_nvme_aer_delta=64
max_nvme_sectors_read_delta=536870912
child=""
launcher=""
server_pid=""
server_pgid=""
journal_follow_pid=""
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

sample_pressure() {
  local now mem_available_kib swap_total_kib aspm_policy nvme_aer_cor root_aer_cor nvme_sectors_read
  local mem_psi_some mem_psi_full io_psi_some io_psi_full vm_fields disk_fields
  now=$(date --iso-8601=ns)
  mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
  swap_total_kib=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
  aspm_policy=$(< /sys/module/pcie_aspm/parameters/policy)
  nvme_aer_cor=$(awk '$1 == "TOTAL_ERR_COR" {print $2}' \
    /sys/bus/pci/devices/0000:01:00.0/aer_dev_correctable)
  root_aer_cor=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor)
  nvme_sectors_read=$(awk '$3 == "nvme0n1" {print $6}' /proc/diskstats)
  mem_psi_some=$(awk '/^some/ {print $2}' /proc/pressure/memory)
  mem_psi_full=$(awk '/^full/ {print $2}' /proc/pressure/memory)
  io_psi_some=$(awk '/^some/ {print $2}' /proc/pressure/io)
  io_psi_full=$(awk '/^full/ {print $2}' /proc/pressure/io)
  vm_fields=$(awk '$1 ~ /^(pgpgin|pgpgout|pswpin|pswpout)$/ {printf "%s=%s,", $1, $2}' /proc/vmstat)
  disk_fields=$(awk '$3 == "nvme0n1" {printf "reads=%s,sectors_read=%s,writes=%s,sectors_written=%s", $4, $6, $8, $10}' /proc/diskstats)
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$now" "$mem_available_kib" "$swap_total_kib" "$nvme_aer_cor" "$root_aer_cor" \
    "$expected_nvme_aer_cor" "$expected_root_aer_cor" \
    "$mem_psi_some" "$mem_psi_full" "$io_psi_some" "$io_psi_full" "$vm_fields" \
    "$disk_fields" "$aspm_policy" >>"$pressure_log"
  (( swap_total_kib == 0 )) || return 1
  [[ "$aspm_policy" == *'[performance]'* ]] || return 1
  (( root_aer_cor == expected_root_aer_cor && nvme_aer_cor >= expected_nvme_aer_cor && \
     nvme_aer_cor - expected_nvme_aer_cor <= max_nvme_aer_delta && \
     nvme_sectors_read >= expected_nvme_sectors_read && \
     nvme_sectors_read - expected_nvme_sectors_read <= max_nvme_sectors_read_delta )) || return 1
  (( mem_available_kib >= 12000000 )) || return 1
  awk -v field="$mem_psi_full" 'BEGIN { split(field, values, "="); exit !(values[2] <= 10.0) }' || return 1
  ! grep -Eqi 'event severity: (fatal|recoverable)|uncorrected|DPC:|link down|controller is down' \
    "${evidence_dir}/kernel-follow.log" || return 1
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
  if [[ "$journal_follow_pid" =~ ^[1-9][0-9]*$ ]] && kill -0 "$journal_follow_pid" 2>/dev/null; then
    kill -TERM "$journal_follow_pid" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "$journal_follow_pid" 2>/dev/null || break
      sleep .1
    done
    if ! kill -0 "$journal_follow_pid" 2>/dev/null; then
      wait "$journal_follow_pid" 2>/dev/null || true
    fi
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
  for _ in $(seq 1 10); do
    { [[ -z "$child" ]] || ! kill -0 "$child" 2>/dev/null; } && break
    sleep 1
  done
  if [[ -z "$child" ]] || ! kill -0 "$child" 2>/dev/null; then
    wait "$child" 2>/dev/null || true
  fi
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
  local device memory nvme_aer_cor root_aer_cor nvme_sectors_read
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
  ! grep -Eqi 'event severity: (fatal|recoverable)|uncorrected|DPC:|link down|controller is down' \
    "${evidence_dir}/kernel-journal.log" || return 1
  nvme_aer_cor=$(awk '$1 == "TOTAL_ERR_COR" {print $2}' \
    /sys/bus/pci/devices/0000:01:00.0/aer_dev_correctable) || return 1
  root_aer_cor=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor) || return 1
  nvme_sectors_read=$(awk '$3 == "nvme0n1" {print $6}' /proc/diskstats) || return 1
  (( root_aer_cor == expected_root_aer_cor && nvme_aer_cor >= expected_nvme_aer_cor && \
     nvme_aer_cor - expected_nvme_aer_cor <= max_nvme_aer_delta && \
     nvme_sectors_read >= expected_nvme_sectors_read && \
     nvme_sectors_read - expected_nvme_sectors_read <= max_nvme_sectors_read_delta )) || return 1
  (( $(awk '/^SwapTotal:/ {print $2}' /proc/meminfo) == 0 )) || return 1
  grep -Fq '[performance]' /sys/module/pcie_aspm/parameters/policy || return 1
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
[[ "$expected_nvme_aer_cor" =~ ^[0-9]+$ && "$expected_root_aer_cor" =~ ^[0-9]+$ && \
   "$expected_nvme_sectors_read" =~ ^[0-9]+$ ]] || {
  printf 'FAIL: A93 supervisor requires numeric host-control AER baselines\n' >&2
  exit 1
}
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]] || {
  printf 'FAIL: frozen PLE-only wrapper hash changed\n' >&2
  exit 1
}
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]] || {
  printf 'FAIL: frozen PLE-only client hash changed\n' >&2
  exit 1
}
for path in "${state}.pid" "${state}.child.pid" "${state}.launcher.pid" \
  "${state}.server.pid" "${state}.server.pgid" "${state}.rc" "$stop_file" \
  "$failure_file" "${state}.deadline-epoch" "$run_dir" "$cache_dir" "$compile_dir" "$rpc_dir" "$evidence_dir"; do
  [[ ! -e "$path" ]] || { printf 'FAIL: refusing to reuse %s\n' "$path" >&2; exit 1; }
done

mkdir -p "$evidence_dir"
write_atomic "${evidence_dir}/journal-start-epoch.txt" "$journal_start_epoch"
printf 'timestamp\tmem_available_kib\tswap_total_kib\tnvme_aer_corrected\troot_aer_corrected\tnvme_aer_baseline\troot_aer_baseline\tmemory_psi_some\tmemory_psi_full\tio_psi_some\tio_psi_full\tvmstat\tnvme_diskstats\taspm_policy\n' >"$pressure_log"
printf 'nvme_aer_baseline=%s\nroot_aer_baseline=%s\nnvme_sectors_read_baseline=%s\n' \
  "$expected_nvme_aer_cor" "$expected_root_aer_cor" "$expected_nvme_sectors_read" >"${evidence_dir}/aer-baseline.txt"
: >"${evidence_dir}/kernel-follow.log"
journalctl -kf -n 0 --no-pager >"${evidence_dir}/kernel-follow.log" 2>&1 &
journal_follow_pid=$!
if ! sample_pressure; then
  kill -TERM "$journal_follow_pid" 2>/dev/null || true
  wait "$journal_follow_pid" 2>/dev/null || true
  journal_follow_pid=""
  printf 'FAIL: initial A93 host-pressure gate failed\n' >&2
  exit 1
fi
write_atomic "${state}.deadline-epoch" "$deadline_epoch"
write_atomic "${state}.pid" "$$"
started=1
set +e
timeout --signal=TERM --kill-after=30s 10000s env -i \
  HOME=/home/steve USER=steve LOGNAME=steve LANG=C.UTF-8 \
  Q38_A93_NVME_AER_BASELINE="$expected_nvme_aer_cor" \
  Q38_A93_ROOT_AER_BASELINE="$expected_root_aer_cor" \
  Q38_A93_NVME_SECTORS_READ_BASELINE="$expected_nvme_sectors_read" \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  "$wrapper" &
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
  if ! sample_pressure; then
    write_atomic "$failure_file" 'FAIL A93 host-pressure or NVMe-link guard'
  fi
  if [[ -e "$stop_file" || -e "$failure_file" ]]; then
    requested_stop=1
    if [[ -e "$stop_file" && ! -e "$failure_file" ]] && \
       [[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]] && \
       grep -Fxq 'STOP after passed PLE-only 2K MTP0 QSA-stable treatment' "$stop_file" && \
       grep -Fxq 'PASS recovery quality short-repeat exact-2K-repeat PLE-only 2K MTP0 QSA-stable treatment' \
         "${run_dir}/client-gates-passed.txt" 2>/dev/null && \
       jq -e '.status == "passed" and .phase == "after" and
         .size_1_full_dispatch_count > 0 and
         (.collective_processes | length) >= 4 and
         .libccl.sha256 == "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700" and
         .ccl_kernel.sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and
         .ccl_sycl_allreduce_ll == "twoshots" and
         .schema_version == 2 and .compilation_mode == "NONE" and
         .inductor_disabled_receipts > 0 and
         .torchinductor_cache.interpretation == "trace_attributed_nested_operator_cache" and
         .torchinductor_cache.file_count > 0 and
         .torch_trace.compile_event_count > 0' \
         "${run_dir}/fullgraphdet-runtime-after.json" >/dev/null 2>&1 && \
       jq -e '.status == "passed" and .recovery_canary == "passed" and
         .identity.model_revision == "bcd9f01ddc9cff2316eb84281bebcd5b058bddce" and
         .identity.vllm_head == "cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9" and
         .identity.kernel_head == "e421889999bc1e5a5f11044d14548b9afdba644d" and
         .identity.stage_build_head == "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4" and
         .identity.tp == 4 and .identity.ep == 4 and .identity.mtp == 1 and
         .identity.graph == "FULL_DECODE_ONLY" and
.identity.compilation_mode == "NONE" and
.identity.cudagraph_capture_sizes == [1,2] and
.identity.max_model_len == 4352 and
         .identity.placement == "ple_only_uva" and
         .identity.async_uva_ple_prefetch == false and
         .identity.libccl_sha256 == "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700" and
         .identity.ccl_kernel_sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and
         .identity.ccl_sycl_allreduce_ll == "twoshots" and
         .identity.tuned_config_folder == "moe-m1-w13-n32" and
         .identity.tuned_config_map_sha256 == "a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be" and
         .identity.ple_host_bytes_per_rank == 12800061440 and
         .identity.input_embedding == "device" and
         .identity.diagnostics == "full-decode-graph-public-oneccl-torch-trace" and
         .identity.torch_trace_policy == "dynamo-exact-target-allowlist-v1" and
         .identity.kv_cache_memory_bytes == 376569856 and
         .exact_2k.repeats == 2 and .exact_2k.same_boot_output_repeat == true and
         .exact_2k.cached_tokens == [0, 0] and
         .exact_2k.output_token_ids_sha256 == "5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e" and
         .short.output_sha256 == "5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0" and
         .protected_results_changed == false' \
         "${run_dir}/ple-only-qsa-stable-summary.json" >/dev/null 2>&1; then
      valid_stop=1
    fi
    kill -TERM "$launcher" 2>/dev/null || true
    break
  fi
  sleep 1
done
set +e
wait "$child"
child_rc=$?
set -e
cleanup_owned
final_pressure_ok=0
if sample_pressure; then
  final_pressure_ok=1
else
  write_atomic "$failure_file" 'FAIL A93 final host-pressure or NVMe-link guard'
fi
rc=$child_rc
if (( requested_stop == 1 && valid_stop == 1 && final_pressure_ok == 1 )) && \
   [[ ! -e "$failure_file" ]]; then rc=0; fi
(( rc != 0 )) || { (( valid_stop == 1 && final_pressure_ok == 1 )) && [[ ! -e "$failure_file" ]]; } || rc=70
write_atomic "${state}.rc" "$rc"
capture_postflight
if ! postflight_clean; then
  printf 'FAIL: PLE-only postflight was not clean\n' >&2
  rc=70
  write_atomic "${state}.rc" "$rc"
fi
write_atomic "${evidence_dir}/final.rc" "$rc"
finished=1
exit "$rc"
