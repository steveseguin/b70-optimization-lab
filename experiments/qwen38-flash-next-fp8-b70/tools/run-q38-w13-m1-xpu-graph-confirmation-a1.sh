#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
vllm=/home/steve/src/vllm-current-main
kernels=/home/steve/src/vllm-xpu-kernels
python=/home/steve/.venvs/vllm-xpu/bin/python3
stage_root=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
stage="${stage_root}/vllm_xpu_kernels"
model=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8
tool="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/w13-m1-xpu-graph-gate.py"
summarizer="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/summarize-w13-m1-xpu-graph-confirmation.py"
stage_manifest="${repo}/experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-padding-guard-loadable.sha256"
result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-w13-xpu-graph-confirmation-a1
cache_root=/dev/shm/q38-w13-m1-xpu-graph-confirmation-a1
loader_suffix=/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib
nvme_aer_path=/sys/bus/pci/devices/0000:01:00.0/aer_dev_correctable
root_aer_path=/sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor

model_revision=bcd9f01ddc9cff2316eb84281bebcd5b058bddce
expected_vllm=cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9
expected_kernels=e421889999bc1e5a5f11044d14548b9afdba644d
expected_tool=8828a3b42766a96f014299967af94cbde48410abd92d64183685dbf737ce05a1
expected_summarizer=fd403e8f5435612b9f1216598947ee156cdf2f2f4de5a72de5bfea5dbd8355e0
expected_stage_manifest=9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b
expected_fused_moe=4b376eb5e22e7972a1d70e4012999650ab961719d6309cbec27a6104fa64d0a0
expected_triton_moe=b8a461b712b88cf6ab5ba4f49029fddce3a501f7ff909b276b6de04b808da4c2
expected_modular_kernel=1e60aca6ed0dd4fcb46d577897ff1651f27a6130b3449d22265c0c791beec5d5
expected_model_index=0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6
expected_model_config=99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d
expected_receipt=4299f69d6231afaf0874de85f15bfa6ffc3c5fb97a4853f04ddffb5504d57dbc
max_nvme_aer_delta=16
max_nvme_sectors_read_delta=4194304
min_mem_available_kib=96000000
max_memory_full_avg10=0.10
max_total_seconds=10800

shard_names=(
  model-00002-of-00131.safetensors
  model-00003-of-00131.safetensors
  model-00119-of-00131.safetensors
  model-00120-of-00131.safetensors
)
shard_sizes=(1678209208 993901136 1678211256 1109903856)
shard_hashes=(
  6841fe21fa8a8a7a693c585efe65cd2732889095b696da88bda0cb287366910b
  974a2a2ab551f8f1405a4955ab32a8721c68c73dd85b382491d9f0e6a34ee752
  36008b48c4480085bfd1a81439d70d1029cfaf06cfdd037cec19b491a40659ec
  49e4f90d92f60f6489bfe6d3e5250d8fe879c5995ae72ce67379cc7187fa4b0a
)

started=0
active_pgid=""
journal_follow_pid=""
journal_start_epoch=""
deadline_epoch=""
nvme_aer_baseline=""
root_aer_baseline=""
nvme_sectors_read_baseline=""
health_failure_reason=""

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
digest() { sha256sum "$1" | cut -d' ' -f1; }
require_hash() {
  local path=$1 expected=$2 label=$3
  [[ -f "$path" && "$(digest "$path")" == "$expected" ]] || fail "$label drifted"
}
current_nvme_aer() { awk '$1 == "TOTAL_ERR_COR" {print $2}' "$nvme_aer_path"; }
current_root_aer() { awk 'NR == 1 {print $1}' "$root_aer_path"; }
current_nvme_sectors_read() { awk '$3 == "nvme0n1" {print $6}' /proc/diskstats; }

health_ok() {
  local now nvme root nvme_delta root_delta nvme_sectors nvme_sectors_delta
  local severe_count swap_used_kib mem_available_kib memory_full_avg10
  [[ "$journal_follow_pid" =~ ^[1-9][0-9]*$ ]] && kill -0 "$journal_follow_pid" 2>/dev/null || {
    health_failure_reason="kernel journal follower stopped"
    return 1
  }
  now=$(date --iso-8601=ns)
  nvme=$(current_nvme_aer 2>/dev/null || true)
  root=$(current_root_aer 2>/dev/null || true)
  nvme_sectors=$(current_nvme_sectors_read 2>/dev/null || true)
  [[ "$nvme" =~ ^[0-9]+$ && "$root" =~ ^[0-9]+$ && "$nvme_sectors" =~ ^[0-9]+$ ]] || {
    health_failure_reason="non-numeric corrected-event counter"
    return 1
  }
  (( nvme >= nvme_aer_baseline && root >= root_aer_baseline )) || {
    health_failure_reason="corrected-event counter moved backwards"
    return 1
  }
  nvme_delta=$((nvme - nvme_aer_baseline))
  root_delta=$((root - root_aer_baseline))
  (( nvme_sectors >= nvme_sectors_read_baseline )) || {
    health_failure_reason="local-NVMe read counter moved backwards"
    return 1
  }
  nvme_sectors_delta=$((nvme_sectors - nvme_sectors_read_baseline))
  swap_used_kib=$(awk '/^SwapTotal:/ {total=$2} /^SwapFree:/ {free=$2} END {print total-free}' /proc/meminfo)
  mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
  memory_full_avg10=$(awk '/^full/ {split($2, value, "="); print value[2]}' /proc/pressure/memory)
  severe_count=$(grep -Eci \
    'event severity: (fatal|recoverable)|uncorrected|DPC:|link down|controller is down|xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
    "${result}/kernel-follow.log" 2>/dev/null || true)
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$now" "$nvme" "$nvme_delta" "$root" "$root_delta" "$nvme_sectors" \
    "$nvme_sectors_delta" "$swap_used_kib" "$mem_available_kib" \
    "$memory_full_avg10" "$severe_count" \
    >>"${result}/health-samples.tsv"
  (( nvme_delta <= max_nvme_aer_delta )) || {
    health_failure_reason="local-NVMe corrected-event delta exceeded ${max_nvme_aer_delta}"
    return 1
  }
  (( root_delta == 0 )) || {
    health_failure_reason="root-port corrected-event delta was nonzero"
    return 1
  }
  (( nvme_sectors_delta <= max_nvme_sectors_read_delta )) || {
    health_failure_reason="local-NVMe read delta exceeded ${max_nvme_sectors_read_delta} sectors"
    return 1
  }
  (( swap_used_kib == 0 )) || {
    health_failure_reason="swap use became nonzero"
    return 1
  }
  (( mem_available_kib >= min_mem_available_kib )) || {
    health_failure_reason="MemAvailable fell below ${min_mem_available_kib} KiB"
    return 1
  }
  awk -v value="$memory_full_avg10" -v maximum="$max_memory_full_avg10" \
    'BEGIN { exit !(value >= 0 && value <= maximum) }' || {
    health_failure_reason="memory full avg10 exceeded ${max_memory_full_avg10}"
    return 1
  }
  (( severe_count == 0 )) || {
    health_failure_reason="severe kernel event appeared"
    return 1
  }
  (( $(date +%s) <= deadline_epoch )) || {
    health_failure_reason="confirmation exceeded ${max_total_seconds}-second deadline"
    return 1
  }
}

stop_active() {
  if [[ "$active_pgid" =~ ^[1-9][0-9]*$ ]] && kill -0 "$active_pgid" 2>/dev/null; then
    kill -TERM -- "-${active_pgid}" 2>/dev/null || true
    for _ in $(seq 1 50); do
      kill -0 "$active_pgid" 2>/dev/null || break
      sleep .1
    done
    kill -KILL -- "-${active_pgid}" 2>/dev/null || true
    wait "$active_pgid" 2>/dev/null || true
  fi
  active_pgid=""
}

finalize() {
  local rc=$? journal_rc=0 final_nvme final_root nvme_delta root_delta severe_count status
  local final_nvme_sectors nvme_sectors_delta swap_used_kib mem_available_kib
  local memory_full_avg10 cache_teardown_complete=0 owned_process_teardown_complete=1
  local receipt_write_rc=0 recorded_receipt_rc rewrite_ok=0
  trap - EXIT INT TERM HUP
  set +e
  stop_active
  set +e
  if [[ "$journal_follow_pid" =~ ^[1-9][0-9]*$ ]] && kill -0 "$journal_follow_pid" 2>/dev/null; then
    kill -TERM "$journal_follow_pid" 2>/dev/null || true
    wait "$journal_follow_pid" 2>/dev/null || true
  fi
  if (( started == 1 )); then
    if pgrep -af 'w13-m1-xpu-graph-gate.py' >"${result}/component-processes-after.txt" 2>&1; then
      owned_process_teardown_complete=0
    fi
    if [[ -d "$cache_root" ]]; then
      find "$cache_root" -mindepth 1 -delete 2>/dev/null || true
      rmdir "$cache_root" 2>/dev/null || true
    fi
    [[ ! -e "$cache_root" ]] && cache_teardown_complete=1
    journalctl -k --since "@${journal_start_epoch}" --no-pager \
      >"${result}/kernel-journal-final.log" 2>"${result}/kernel-journal-final.err"
    journal_rc=$?
    final_nvme=$(current_nvme_aer 2>/dev/null || printf '%s' -1)
    final_root=$(current_root_aer 2>/dev/null || printf '%s' -1)
    final_nvme_sectors=$(current_nvme_sectors_read 2>/dev/null || printf '%s' -1)
    swap_used_kib=$(awk '/^SwapTotal:/ {total=$2} /^SwapFree:/ {free=$2} END {print total-free}' /proc/meminfo)
    mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    memory_full_avg10=$(awk '/^full/ {split($2, value, "="); print value[2]}' /proc/pressure/memory)
    if [[ "$final_nvme" =~ ^[0-9]+$ && "$final_root" =~ ^[0-9]+$ ]]; then
      nvme_delta=$((final_nvme - nvme_aer_baseline))
      root_delta=$((final_root - root_aer_baseline))
    else
      nvme_delta=-1
      root_delta=-1
    fi
    if [[ "$final_nvme_sectors" =~ ^[0-9]+$ && "$nvme_sectors_read_baseline" =~ ^[0-9]+$ && \
          "$final_nvme_sectors" -ge "$nvme_sectors_read_baseline" ]]; then
      nvme_sectors_delta=$((final_nvme_sectors - nvme_sectors_read_baseline))
    else
      nvme_sectors_delta=-1
    fi
    severe_count=$(grep -Eci \
      'event severity: (fatal|recoverable)|uncorrected|DPC:|link down|controller is down|xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
      "${result}/kernel-journal-final.log" 2>/dev/null || true)
    if (( journal_rc != 0 || nvme_delta < 0 || nvme_delta > max_nvme_aer_delta || \
          root_delta != 0 || nvme_sectors_delta < 0 || \
          nvme_sectors_delta > max_nvme_sectors_read_delta || swap_used_kib != 0 || \
          mem_available_kib < min_mem_available_kib || severe_count != 0 || \
          cache_teardown_complete != 1 || owned_process_teardown_complete != 1 )) || \
       ! awk -v value="$memory_full_avg10" -v maximum="$max_memory_full_avg10" \
         'BEGIN { exit !(value >= 0 && value <= maximum) }'; then
      [[ -n "$health_failure_reason" ]] || health_failure_reason="final health contract failed"
      (( rc != 0 )) || rc=70
    fi
    timeout 30s xpu-smi discovery -j >"${result}/device-discovery-final.json" \
      2>"${result}/device-discovery-final.err" || true
    if ! find "$result" -maxdepth 1 -type f \
      ! -name 'SHA256SUMS*' ! -name health-receipt.json -print0 | sort -z | \
      xargs -0 sha256sum >"${result}/SHA256SUMS.tmp"; then
      [[ -n "$health_failure_reason" ]] || health_failure_reason="final evidence hashing failed"
      (( rc != 0 )) || rc=70
    fi
    status=failed_closed
    (( rc == 0 )) && status=pass
    "$python" - "$result" "$status" "$rc" "$journal_rc" \
      "$nvme_aer_baseline" "$final_nvme" "$nvme_delta" "$max_nvme_aer_delta" \
      "$root_aer_baseline" "$final_root" "$root_delta" "$severe_count" \
      "$nvme_sectors_read_baseline" "$final_nvme_sectors" "$nvme_sectors_delta" \
      "$max_nvme_sectors_read_delta" "$swap_used_kib" "$mem_available_kib" \
      "$memory_full_avg10" "$max_memory_full_avg10" "$cache_teardown_complete" \
      "$owned_process_teardown_complete" "$health_failure_reason" <<'PY'
import json
from pathlib import Path
import sys

(root, status, rc, journal_rc, nvme_before, nvme_after, nvme_delta, nvme_cap,
 root_before, root_after, root_delta, severe_count, sectors_before,
 sectors_after, sectors_delta, sectors_cap, swap_used, mem_available,
 memory_full_avg10, memory_full_cap, cache_teardown, process_teardown,
 reason) = sys.argv[1:]
value = {
    "schema_version": 1,
    "status": status,
    "classification": "qwen38_w13_confirmation_host_health",
    "dynamic_baseline": True,
    "local_nvme_corrected": {
        "baseline": int(nvme_before), "final": int(nvme_after),
        "delta": int(nvme_delta), "maximum_delta": int(nvme_cap),
    },
    "root_port_corrected": {
        "baseline": int(root_before), "final": int(root_after),
        "delta": int(root_delta), "required_delta": 0,
    },
    "local_nvme_sectors_read": {
        "baseline": int(sectors_before), "final": int(sectors_after),
        "delta": int(sectors_delta), "maximum_delta": int(sectors_cap),
    },
    "swap_used_kib": int(swap_used),
    "mem_available_kib": int(mem_available),
    "memory_full_avg10": float(memory_full_avg10),
    "maximum_memory_full_avg10": float(memory_full_cap),
    "severe_event_count": int(severe_count),
    "journal_capture_exit_code": int(journal_rc),
    "runner_exit_code": int(rc),
    "failure_reason": reason or None,
    "owned_process_teardown_complete": bool(int(process_teardown)),
    "cache_teardown_complete": bool(int(cache_teardown)),
}
Path(root, "health-receipt.json").write_text(
    json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
    encoding="utf-8",
)
PY
    receipt_write_rc=$?
    if (( receipt_write_rc != 0 )) || \
       ! jq -e --arg status "$status" --argjson rc "$rc" '
          .classification == "qwen38_w13_confirmation_host_health" and
          .status == $status and .runner_exit_code == $rc and
          .dynamic_baseline == true and
          .local_nvme_corrected.maximum_delta == 16 and
          .root_port_corrected.required_delta == 0 and
          .local_nvme_sectors_read.maximum_delta == 4194304 and
          .owned_process_teardown_complete == true and
          .cache_teardown_complete == true
       ' "${result}/health-receipt.json" >/dev/null; then
      [[ -n "$health_failure_reason" ]] || health_failure_reason="health receipt write or verification failed"
      (( rc != 0 )) || rc=70
    fi
    if [[ -f "${result}/SHA256SUMS.tmp" && -f "${result}/health-receipt.json" ]] && \
       sha256sum "${result}/health-receipt.json" >>"${result}/SHA256SUMS.tmp" && \
       mv "${result}/SHA256SUMS.tmp" "${result}/SHA256SUMS" && \
       sha256sum -c "${result}/SHA256SUMS" >/dev/null; then
      :
    else
      [[ -n "$health_failure_reason" ]] || health_failure_reason="final SHA256SUMS generation or verification failed"
      (( rc != 0 )) || rc=70
    fi
    if (( rc == 0 )) && \
       { ! jq -e '.status == "pass" and .runner_exit_code == 0' \
           "${result}/health-receipt.json" >/dev/null || \
         ! sha256sum -c "${result}/SHA256SUMS" >/dev/null; }; then
      health_failure_reason="final zero-exit receipt or checksum verification failed"
      rc=70
    fi
    recorded_receipt_rc=$(jq -er '.runner_exit_code' "${result}/health-receipt.json" 2>/dev/null || printf invalid)
    if [[ "$recorded_receipt_rc" != "$rc" ]]; then
      (( rc != 0 )) || rc=70
      [[ -n "$health_failure_reason" ]] || health_failure_reason="late finalization receipt mismatch"
      status=failed_closed
      if [[ -f "${result}/health-receipt.json" ]]; then
        if ! mv "${result}/health-receipt.json" \
          "${result}/health-receipt-pre-final-invalid.json"; then
          rm -f "${result}/health-receipt.json"
        fi
      fi
      rewrite_ok=0
      if [[ -f "${result}/health-receipt-pre-final-invalid.json" ]] && \
         jq --argjson rc "$rc" --arg reason "$health_failure_reason" '
           .status = "failed_closed" |
           .runner_exit_code = $rc |
           .failure_reason = (if $reason == "" then "late final-evidence failure" else $reason end)
         ' "${result}/health-receipt-pre-final-invalid.json" \
           >"${result}/health-receipt.json.tmp"; then
        rewrite_ok=1
      elif jq -n --argjson rc "$rc" --arg reason "$health_failure_reason" \
        --argjson journal_rc "$journal_rc" --argjson nvme_before "$nvme_aer_baseline" \
        --argjson nvme_after "$final_nvme" --argjson nvme_delta "$nvme_delta" \
        --argjson root_before "$root_aer_baseline" --argjson root_after "$final_root" \
        --argjson root_delta "$root_delta" --argjson sectors_before "$nvme_sectors_read_baseline" \
        --argjson sectors_after "$final_nvme_sectors" --argjson sectors_delta "$nvme_sectors_delta" \
        --argjson swap_used "$swap_used_kib" --argjson mem_available "$mem_available_kib" \
        --argjson memory_full "$memory_full_avg10" --argjson severe_count "$severe_count" '
          {
            schema_version: 1,
            status: "failed_closed",
            classification: "qwen38_w13_confirmation_host_health",
            dynamic_baseline: true,
            local_nvme_corrected: {baseline: $nvme_before, final: $nvme_after, delta: $nvme_delta, maximum_delta: 16},
            root_port_corrected: {baseline: $root_before, final: $root_after, delta: $root_delta, required_delta: 0},
            local_nvme_sectors_read: {baseline: $sectors_before, final: $sectors_after, delta: $sectors_delta, maximum_delta: 4194304},
            swap_used_kib: $swap_used,
            mem_available_kib: $mem_available,
            memory_full_avg10: $memory_full,
            maximum_memory_full_avg10: 0.10,
            severe_event_count: $severe_count,
            journal_capture_exit_code: $journal_rc,
            runner_exit_code: $rc,
            failure_reason: (if $reason == "" then "late final-evidence failure" else $reason end),
            owned_process_teardown_complete: false,
            cache_teardown_complete: false
          }
        ' >"${result}/health-receipt.json.tmp"; then
        rewrite_ok=1
      fi
      if (( rewrite_ok == 1 )) && \
         mv "${result}/health-receipt.json.tmp" "${result}/health-receipt.json" && \
         jq -e --argjson rc "$rc" '
           .status == "failed_closed" and .runner_exit_code == $rc
         ' "${result}/health-receipt.json" >/dev/null; then
        if find "$result" -maxdepth 1 -type f ! -name 'SHA256SUMS*' -print0 | \
             sort -z | xargs -0 sha256sum >"${result}/SHA256SUMS.tmp" && \
           mv "${result}/SHA256SUMS.tmp" "${result}/SHA256SUMS" && \
           sha256sum -c "${result}/SHA256SUMS" >/dev/null; then
          :
        else
          rm -f "${result}/SHA256SUMS.tmp"
        fi
      else
        rm -f "${result}/health-receipt.json.tmp" "${result}/SHA256SUMS.tmp"
      fi
    fi
  fi
  exit "$rc"
}
trap finalize EXIT
trap 'exit 130' INT TERM HUP

[[ $# == 0 ]] || fail "this frozen confirmation takes no arguments"
[[ "${Q38_W13_CONFIRM_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
[[ -x "$python" ]] || fail "vLLM XPU interpreter is missing"
require_hash "$tool" "$expected_tool" "W13 component gate"
require_hash "$summarizer" "$expected_summarizer" "W13 confirmation summarizer"
require_hash "$stage_manifest" "$expected_stage_manifest" "runtime-stage manifest"
require_hash "${vllm}/vllm/model_executor/layers/fused_moe/fused_moe.py" "$expected_fused_moe" "fused MoE source"
require_hash "${vllm}/vllm/model_executor/layers/fused_moe/experts/triton_moe.py" "$expected_triton_moe" "Triton MoE source"
require_hash "${vllm}/vllm/model_executor/layers/fused_moe/modular_kernel.py" "$expected_modular_kernel" "modular MoE source"
require_hash "${model}/model.safetensors.index.json" "$expected_model_index" "model index"
require_hash "${model}/config.json" "$expected_model_config" "model config"
[[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" ]] || fail "vLLM head drifted"
[[ -z "$(git -C "$vllm" status --porcelain --untracked-files=no)" ]] || fail "vLLM tracked source is dirty"
[[ "$(git -C "$kernels" rev-parse HEAD)" == "$expected_kernels" ]] || fail "kernel head drifted"
[[ -z "$(git -C "$kernels" status --porcelain --untracked-files=no)" ]] || fail "kernel tracked source is dirty"
(cd "$stage" && sha256sum -c "$stage_manifest") >/dev/null || fail "runtime-stage files drifted"
read -r model_source model_type model_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target "$model")
[[ "$model_source" == /dev/sda2 && "$model_type" == fuseblk && "$model_target" == /mnt/usb-models ]] || fail "model is not on the frozen external filesystem"
read -r shm_type shm_target < <(findmnt -nro FSTYPE,TARGET --target /dev/shm)
[[ "$shm_type" == tmpfs && "$shm_target" == /dev/shm ]] || fail "/dev/shm is not the frozen tmpfs cache filesystem"

if [[ "${Q38_W13_CONFIRM_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: frozen W13 N32 graph confirmation validates without GPU work\n'
  exit 0
fi

[[ -f "$nvme_aer_path" && -f "$root_aer_path" ]] || fail "corrected-event counters are missing"
[[ ! -e "$result" ]] || fail "evidence root already exists"
[[ ! -e "$cache_root" ]] || fail "exclusive /dev/shm cache root already exists"
[[ -z "$(pgrep -af 'vllm serve|VLLM::EngineCore|Worker_TP|w13-m1-xpu-graph-gate.py' || true)" ]] || fail "a model or W13 component process is active"
exec 9>/tmp/q38-w13-m1-xpu-graph-confirmation-a1.lock
flock -n 9 || fail "another W13 graph confirmation owns the lock"

mkdir -p "$result"
started=1
install -m 0644 "$0" "${result}/runner.sh"
journal_start_epoch=$(date +%s)
deadline_epoch=$((journal_start_epoch + max_total_seconds))
nvme_aer_baseline=$(current_nvme_aer)
root_aer_baseline=$(current_root_aer)
nvme_sectors_read_baseline=$(current_nvme_sectors_read)
[[ "$nvme_aer_baseline" =~ ^[0-9]+$ && "$root_aer_baseline" =~ ^[0-9]+$ && \
   "$nvme_sectors_read_baseline" =~ ^[0-9]+$ ]] || fail "could not establish dynamic host baselines"
printf 'timestamp\tnvme_corrected\tnvme_delta\troot_corrected\troot_delta\tnvme_sectors_read\tnvme_sectors_delta\tswap_used_kib\tmem_available_kib\tmemory_full_avg10\tsevere_events\n' >"${result}/health-samples.tsv"
: >"${result}/kernel-follow.log"
journalctl -kf -n 0 --no-pager >"${result}/kernel-follow.log" 2>&1 &
journal_follow_pid=$!
sleep .2
kill -0 "$journal_follow_pid" 2>/dev/null || fail "kernel journal follower did not remain active"
health_ok || fail "$health_failure_reason"

for _ in $(seq 1 60); do
  sleep 1
  health_ok || fail "$health_failure_reason"
  [[ "$(current_nvme_aer)" == "$nvme_aer_baseline" && \
     "$(current_root_aer)" == "$root_aer_baseline" ]] || \
    fail "corrected-event counter changed during the 60-second idle preflight"
done
printf 'PASS: 60-second idle preflight had zero corrected-event change\n' >"${result}/idle-preflight.txt"

mkdir -m 0700 "$cache_root"
for directory in triton vllm torchinductor xdg torch-extensions tmp; do
  mkdir -m 0700 "${cache_root}/${directory}"
done
[[ -w "$cache_root" ]] || fail "exclusive /dev/shm cache root is not writable"

for index in "${!shard_names[@]}"; do
  shard=${shard_names[$index]}
  [[ "$(stat -c %s "${model}/${shard}")" == "${shard_sizes[$index]}" ]] || fail "${shard} size drifted"
  require_hash "${model}/${shard}" "${shard_hashes[$index]}" "${shard}"
  health_ok || fail "$health_failure_reason"
done

"$python" - "$model" "${result}/checkpoint-receipt.json" <<'PY'
import json
from pathlib import Path
import sys

model = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2])
shards = {
    "model-00002-of-00131.safetensors": (1678209208, "6841fe21fa8a8a7a693c585efe65cd2732889095b696da88bda0cb287366910b", 2050, 1802503, 1787754541759779900, 1787754541796499200),
    "model-00003-of-00131.safetensors": (993901136, "974a2a2ab551f8f1405a4955ab32a8721c68c73dd85b382491d9f0e6a34ee752", 2050, 1802510, 1787754136121899500, 1787754136146451600),
    "model-00119-of-00131.safetensors": (1678211256, "36008b48c4480085bfd1a81439d70d1029cfaf06cfdd037cec19b491a40659ec", 2050, 960115, 1787777584386745100, 1787777584401268900),
    "model-00120-of-00131.safetensors": (1109903856, "49e4f90d92f60f6489bfe6d3e5250d8fe879c5995ae72ce67379cc7187fa4b0a", 2050, 960127, 1787777583721158000, 1787777583828473400),
}
checkpoint_shards = {}
for name, (size, digest, device, inode, mtime_ns, ctime_ns) in shards.items():
    path = model / name
    file_stat = path.stat()
    stat_identity = {
        "device": file_stat.st_dev,
        "inode": file_stat.st_ino,
        "mtime_ns": file_stat.st_mtime_ns,
        "ctime_ns": file_stat.st_ctime_ns,
    }
    expected_stat = {
        "device": device,
        "inode": inode,
        "mtime_ns": mtime_ns,
        "ctime_ns": ctime_ns,
    }
    if stat_identity != expected_stat or file_stat.st_size != size:
        raise SystemExit(f"frozen stat identity drifted for {name}")
    checkpoint_shards[name] = {
        "path": str(path),
        "size": size,
        "sha256": digest,
        "stat_identity": stat_identity,
    }
value = {
    "schema_version": 1,
    "status": "pass",
    "classification": "qwen38_w13_checkpoint_checksum_receipt",
    "model_path": str(model),
    "model_revision": "bcd9f01ddc9cff2316eb84281bebcd5b058bddce",
    "model_index_sha256": "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6",
    "model_config_sha256": "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d",
    "checkpoint_shards": checkpoint_shards,
}
output.write_text(
    json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
    encoding="utf-8",
)
PY
receipt_sha=$(digest "${result}/checkpoint-receipt.json")
[[ "$receipt_sha" == "$expected_receipt" ]] || fail "checkpoint receipt drifted"
printf '%s\n' "$receipt_sha" >"${result}/checkpoint-receipt.sha256"

xpu-smi discovery -j >"${result}/device-discovery.json"
jq -e '.device_list | length == 4 and all(.[]; .device_name == "Intel(R) Arc(TM) Pro B70 Graphics")' \
  "${result}/device-discovery.json" >/dev/null || fail "four-B70 discovery failed"
{
  printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id)"
  printf 'model_revision=%s\n' "$model_revision"
  printf 'vllm_head=%s\n' "$expected_vllm"
  printf 'kernel_head=%s\n' "$expected_kernels"
  printf 'runner_sha256=%s\n' "$(digest "$0")"
  printf 'tool_sha256=%s\n' "$expected_tool"
  printf 'summarizer_sha256=%s\n' "$expected_summarizer"
  printf 'checkpoint_receipt_sha256=%s\n' "$receipt_sha"
  printf 'nvme_corrected_dynamic_baseline=%s\n' "$nvme_aer_baseline"
  printf 'root_corrected_dynamic_baseline=%s\n' "$root_aer_baseline"
  printf 'local_nvme_sectors_read_dynamic_baseline=%s\n' "$nvme_sectors_read_baseline"
  printf 'local_nvme_corrected_delta_cap=%s\n' "$max_nvme_aer_delta"
  printf 'root_corrected_required_delta=0\n'
  printf 'local_nvme_sectors_read_delta_cap=%s\n' "$max_nvme_sectors_read_delta"
  printf 'minimum_mem_available_kib=%s\n' "$min_mem_available_kib"
  printf 'maximum_memory_full_avg10=%s\n' "$max_memory_full_avg10"
  printf 'exclusive_cache_root=%s\n' "$cache_root"
  printf 'scope=layers0,47 ranks0-3 seeds20260826,20260827,20260830 W13-N32 matched C/A/C\n'
} >"${result}/identity.txt"

run_arm() {
  local label=$1 layer=$2 rank=$3 seed=$4 config=$5 authority=${6:-} allow_failure=${7:-0}
  local log="${result}/${label}.jsonl" err="${result}/${label}.stderr" rc
  local -a command=(
    env -u ZE_AFFINITY_MASK
    ONEAPI_DEVICE_SELECTOR=level_zero:0
    VLLM_TARGET_DEVICE=xpu
    PYTHONHASHSEED=0
    PYTHONNOUSERSITE=1
    PYTHONSAFEPATH=1
    PYTHONDONTWRITEBYTECODE=1
    "TRITON_CACHE_DIR=${cache_root}/triton"
    "VLLM_CACHE_ROOT=${cache_root}/vllm"
    "TORCHINDUCTOR_CACHE_DIR=${cache_root}/torchinductor"
    "XDG_CACHE_HOME=${cache_root}/xdg"
    "TORCH_EXTENSIONS_DIR=${cache_root}/torch-extensions"
    "TMPDIR=${cache_root}/tmp"
    "PYTHONPATH=${stage_root}:${vllm}"
    "LD_LIBRARY_PATH=${stage}:${loader_suffix}"
    "$python" "$tool"
    --model-path "$model"
    --model-revision "$model_revision"
    --layer "$layer"
    --ep-rank "$rank"
    --seed "$seed"
    --hidden-scale 0.01
    --capture-warmups 5
    --timing-warmups 10
    --timing-batches 15
    --iterations-per-batch 200
    --candidate-config-json "$config"
    --checkpoint-receipt-json "${result}/checkpoint-receipt.json"
    --checkpoint-receipt-sha256 "$receipt_sha"
  )
  [[ -z "$authority" ]] || command+=(--control-authority-json "$authority")
  printf '%q ' setsid timeout --signal=TERM --kill-after=30s 420s "${command[@]}" >>"${result}/commands.sh"
  printf '> %q 2> %q\n' "$log" "$err" >>"${result}/commands.sh"
  setsid timeout --signal=TERM --kill-after=30s 420s "${command[@]}" >"$log" 2>"$err" &
  active_pgid=$!
  while kill -0 "$active_pgid" 2>/dev/null; do
    if ! health_ok; then
      printf '%s\n' "$health_failure_reason" >"${result}/health-stop.txt"
      stop_active
      fail "$health_failure_reason"
    fi
    sleep 2
  done
  set +e
  wait "$active_pgid"
  rc=$?
  set -e
  active_pgid=""
  printf '%s\n' "$rc" >"${result}/${label}.exit-code"
  health_ok || fail "$health_failure_reason"
  if (( rc != 0 && allow_failure == 0 )); then
    fail "$label failed with rc ${rc}"
  fi
  return "$rc"
}

validate_arm() {
  local log=$1 layer=$2 rank=$3 seed=$4 config=$5 authority=$6
  jq -e --argjson layer "$layer" --argjson rank "$rank" --argjson seed "$seed" \
    --argjson expected_config "$config" --arg expected_authority "$authority" \
    --arg receipt_path "${result}/checkpoint-receipt.json" --arg receipt_sha "$receipt_sha" '
    .status == "pass" and
    .classification == "qwen38_flash_next_w13_m1_xpu_graph_component" and
    .identity.model_path == "/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8" and
    .identity.model_revision == "bcd9f01ddc9cff2316eb84281bebcd5b058bddce" and
    .identity.layer == $layer and .identity.ep_rank == $rank and .identity.seed == $seed and
    .config_receipt.requested == $expected_config and
    .config_receipt.w2_unchanged == true and
    .weights.checkpoint_checksum_mode == "frozen_receipt" and
    .weights.checkpoint_receipt_path == $receipt_path and
    .weights.checkpoint_receipt_sha256 == $receipt_sha and
    .correctness.exact_replays == 100 and
    .correctness.config_local_eager_graph_equal == true and
    .correctness.matches_control_authority == true and
    .correctness.unique_eager_hashes == 100 and
    .correctness.unique_graph_hashes == 100 and
    .correctness.control_authority_path == (if $expected_authority == "" then null else $expected_authority end) and
    (.graph.event_median_us | isfinite) and .graph.event_median_us > 0 and
    .graph.timing_input_index == 0
  ' < <(tail -n 1 "$log") >/dev/null
}

candidate='{"W1_CONFIG":{"BLOCK_SIZE_N":32}}'
first_cell=1
for layer in 0 47; do
  for rank in 0 1 2 3; do
    for seed in 20260826 20260827 20260830; do
      health_ok || fail "$health_failure_reason"
      cell="l${layer}-r${rank}-s${seed}"
      before="${result}/${cell}-control-before.jsonl"
      run_arm "${cell}-control-before" "$layer" "$rank" "$seed" '{}'
      validate_arm "$before" "$layer" "$rank" "$seed" '{}' '' || fail "${cell} control-before contract failed"
      if (( first_cell == 1 )); then
        printf 'PASS: first actual one-XPU confirmation smoke\n' | tee "${result}/first-smoke.txt"
        first_cell=0
      fi
      candidate_rc=0
      run_arm "${cell}-candidate" "$layer" "$rank" "$seed" "$candidate" "$before" 1 || candidate_rc=$?
      if (( candidate_rc == 0 )); then
        validate_arm "${result}/${cell}-candidate.jsonl" "$layer" "$rank" "$seed" "$candidate" "$before" || fail "${cell} candidate contract failed"
      fi
      run_arm "${cell}-control-after" "$layer" "$rank" "$seed" '{}' "$before"
      validate_arm "${result}/${cell}-control-after.jsonl" "$layer" "$rank" "$seed" '{}' "$before" || fail "${cell} control-after contract failed"
      (( candidate_rc == 0 )) || fail "${cell} candidate failed with rc ${candidate_rc}"
    done
  done
done

"$python" "$summarizer" --result-dir "$result" >"${result}/summary.stdout.jsonl"
jq -e '
  .status == "pass" and
  .classification == "qwen38_w13_m1_xpu_graph_confirmation" and
  (.rows | length) == 24 and
  .gates.all_24_cells_exact == true and
  .gates.all_control_drifts_within_two_percent == true and
  .gates.median_reduction_at_least_three_percent == true and
  .gates.at_least_20_positive_cells == true and
  .gates.no_cell_regressed_more_than_two_percent == true and
  .raw_cross_rank_timings_pooled == false and
  .protected_results_changed == false
' "${result}/summary.json" >/dev/null || fail "confirmation summary failed closed"
health_ok || fail "$health_failure_reason"
printf 'PASS: W13 N32 graph confirmation complete: %s\n' "$result"
