#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a44-fullgraph.sh"
expected_wrapper=981d50ff49bcd605ce6c0792fffc64c5e72b1a3700c2bbcda240d85635056c6b
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a44-fullgraph-client.sh"
expected_client=431ebd4547150668610b9ed0d46574725202a279eedf7412b3d51c7ea1ce2904
state=/tmp/q38-mtp0-ple-only-a44
stop_file="${state}.stop"
failure_file="${state}.failed"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt44
cache_dir=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt44
compile_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt44-compile
rpc_dir=/tmp/q38-ple4k-a44-rpc
evidence_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt44-supervisor
port=19716
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
write_atomic "${state}.deadline-epoch" "$deadline_epoch"
write_atomic "${state}.pid" "$$"
started=1
set +e
timeout --signal=TERM --kill-after=30s 10000s env -i \
  HOME=/home/steve USER=steve LOGNAME=steve LANG=C.UTF-8 \
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
  if [[ -e "$stop_file" || -e "$failure_file" ]]; then
    requested_stop=1
    if [[ -e "$stop_file" ]] && \
       [[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]] && \
       grep -Fxq 'STOP after passed PLE-only 4K MTP0 QSA-stable treatment' "$stop_file" && \
       grep -Fxq 'PASS recovery quality short-repeat exact-4K-repeat PLE-only 4K MTP0 QSA-stable treatment' \
         "${run_dir}/client-gates-passed.txt" 2>/dev/null && \
       jq -e '.status == "passed" and .phase == "after" and
         .size_1_full_dispatch_count > 0 and
         (.collective_processes | length) >= 4 and
         .libccl.sha256 == "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700" and
         .ccl_kernel.sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and
         .schema_version == 2 and .compilation_mode == "NONE" and
         .inductor_disabled_receipts > 0 and
         .torchinductor_cache.interpretation == "trace_attributed_nested_operator_cache" and
         .torchinductor_cache.file_count > 0 and
         .torch_trace.compile_event_count > 0' \
         "${run_dir}/fullgraph-runtime-after.json" >/dev/null 2>&1 && \
       jq -e '.status == "passed" and .recovery_canary == "passed" and
         .identity.model_revision == "bcd9f01ddc9cff2316eb84281bebcd5b058bddce" and
         .identity.vllm_head == "797769b34b6db5c934609b75dc04cc61ec66e5f9" and
         .identity.kernel_head == "e421889999bc1e5a5f11044d14548b9afdba644d" and
         .identity.stage_build_head == "2f829747503c77d4814834dffd0840fb1dd9f75a" and
         .identity.tp == 4 and .identity.ep == 4 and .identity.mtp == 0 and
         .identity.graph == "FULL_DECODE_ONLY" and
.identity.compilation_mode == "NONE" and
.identity.cudagraph_capture_sizes == [1] and
.identity.max_model_len == 4352 and
         .identity.placement == "ple_only_uva" and
         .identity.async_uva_ple_prefetch == false and
         .identity.libccl_sha256 == "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700" and
         .identity.ccl_kernel_sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and
         .identity.ple_host_bytes_per_rank == 12800061440 and
         .identity.input_embedding == "device" and
         .identity.diagnostics == "full-decode-graph-public-oneccl-torch-trace" and
         .identity.torch_trace_policy == "dynamo-exact-target-allowlist-v1" and
         .identity.kv_cache_memory_bytes == 134217728 and
         .exact_4k.repeats == 2 and .exact_4k.same_boot_output_repeat == true and
         .exact_4k.cached_tokens == [0, 0] and
         .exact_4k.output_token_ids_sha256 == "1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc" and
         .short.output_sha256 == "5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0" and
         .protected_results_changed == false' \
         "${run_dir}/ple-only-qsa-stable-summary.json" >/dev/null 2>&1; then
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
  printf 'FAIL: PLE-only postflight was not clean\n' >&2
  rc=70
  write_atomic "${state}.rc" "$rc"
fi
write_atomic "${evidence_dir}/final.rc" "$rc"
finished=1
exit "$rc"
