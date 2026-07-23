#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

repo_root=/home/steve/llm-optimizations
vllm_root=/home/steve/src/deepseek-v4-vllm-xpu-dspark
kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
paths_script="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh"
oracle="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_w1_n64_recovery_nvme.py"
base_gate="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_w1_n128_nvme.py"
xccl_gate="$repo_root/scripts/check-qwen36-xpu-xccl-health.sh"
peer_binary=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-device-lost-recovery-20260723T103343Z/no-reboot-validation/sycl-peer-read-test-oneapi2026
sycl_ls=/opt/intel/oneapi/compiler/2026.0/bin/sycl-ls
umf_library=/opt/intel/oneapi/umf/1.1/lib/libumf.so.1
level_zero_adapter=/opt/intel/oneapi/compiler/2026.0/lib/libur_adapter_level_zero.so.0
level_zero_adapter_v2=/opt/intel/oneapi/compiler/2026.0/lib/libur_adapter_level_zero_v2.so.0
oneapi_runtime_ld_library_path=/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib
evidence_root=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T140038Z

expected_boot_id=0b7f98a5-e50a-46a5-81ea-15938b55317a
tainted_ntfs_boot_id=97dfe56f-f2d8-4e08-a923-2c6007f02381
device_lost_boot_id=c3b56b2b-8ae3-4f1a-991a-210a95df55cb
expected_kernel=7.0.0-28-generic
device_lost_kernel=6.17.0-35-generic
expected_vllm_commit=8936aac144929190c1e53f8b8624ca397ce16f5b
expected_kernel_commit=c59aaadbbfd350c2b5f4ad663e247c2811ae3181
expected_peer_sha256=1ab3b96dd1c7cd46a2e5422b0b6bf705ba5b80f306102e968768f634ee4bf92c
expected_fixture_sha256=478a23508e635c91fa62ff0a4b737016266bc308e8fe60111e81abad3d47c1f6
expected_xpu_extension_sha256=f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8
expected_grouped_gemm_sha256=fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96
expected_paths_script_sha256=99ea295ad3432c5b66aab91a4319f1d6bec827883548be7d10d5d1f77bf01e55
expected_oracle_sha256=17a68130b4552bbcb14db19da4f55beb6d7ddc082c6977ae97ba1982f62ba1fe
expected_base_gate_sha256=c970b12fc46c6c025266a055a30dbc0084db2bcd2d127bac3524449d61de166c
expected_xccl_gate_sha256=b15dd4c248d8c4d7035c2d180b9ecc5354b1b20bdabb0c47c540b5003a1cfb78
expected_model_manifest_sha256=45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac
expected_sycl_ls_sha256=90843629cfe9faaa5b5308524f82399b493b82a64b8db4956284b626d886dfb4
expected_umf_library_sha256=c74cfea0360d09b5072a8227efbc830db36bd57669ca22d190d0fb31fe8e3425
expected_level_zero_adapter_sha256=c0b6d1d3f6f282655a034cfc874f48b2f0196970aea41af372d730bbc2124b48
expected_level_zero_adapter_v2_sha256=bfdf524e1b3ecdd0ee87c3337a768be2b3686e3300765d64dd52d20bd53196b5

reject_pattern='Timedout job:|VM job timed out|Kernel-submitted job timed out|device coredump|GT.*reset|reset (queued|started|done)|TLB.*timeout|GuC.*(fail|error|timeout)|CT.*(fail|error|timeout)|AER:.*(error|fatal|nonfatal)|PCIe Bus Error'

evidence_created=false
started_utc=not-started

early_finalize() {
  local rc=$?
  trap - EXIT
  set +e
  if [[ "$evidence_created" == true ]]; then
    local completed_utc
    completed_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    {
      printf 'exit_status=%s\n' "$rc"
      printf 'started_utc=%s\n' "$started_utc"
      printf 'completed_utc=%s\n' "$completed_utc"
      printf 'early_failure=true\n'
    } > "$evidence_root/final-status.txt"
    (
      cd "$evidence_root" || exit 1
      find . -maxdepth 1 -type f ! -name 'evidence.sha256*' -printf '%P\n' \
        | LC_ALL=C sort \
        | xargs -r sha256sum \
        > evidence.sha256.tmp \
        && mv evidence.sha256.tmp evidence.sha256
    )
    sync "$evidence_root"
  fi
  exit "$rc"
}
trap early_finalize EXIT

# shellcheck source=laguna_nvme_paths.sh
source "$paths_script"
laguna_nvme_prepare_paths
[[ "$LAGUNA_NVME_MODEL_ROOT" == /mnt/fast-ai/llm-models/laguna-s-2.1 ]]
[[ "$LAGUNA_NVME_ARTIFACT_ROOT" == /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1 ]]
laguna_nvme_assert_fresh_run_path "$evidence_root"

if [[ -e "$evidence_root" ]]; then
  echo "recovery evidence root already exists: $evidence_root" >&2
  exit 2
fi
mkdir "$evidence_root"
evidence_created=true

started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' "$started_utc" > "$evidence_root/started-utc.txt"

journalctl -k -b -n 1 --show-cursor --no-pager -o short-iso \
  > "$evidence_root/kernel-baseline.txt"
journal_cursor="$(sed -n 's/^-- cursor: //p' "$evidence_root/kernel-baseline.txt" | tail -1)"
if [[ -z "$journal_cursor" ]]; then
  echo "failed to capture kernel journal cursor" >&2
  exit 3
fi

capture_kernel_delta() {
  local journal_rc grep_rc
  if journalctl -k -b --after-cursor "$journal_cursor" --no-pager \
    -o short-iso > "$evidence_root/kernel-delta.txt"; then
    journal_rc=0
  else
    journal_rc=$?
  fi
  (( journal_rc == 0 )) || return "$journal_rc"
  if grep -Eai "$reject_pattern" "$evidence_root/kernel-delta.txt" \
    > "$evidence_root/kernel-reject-events.txt"; then
    grep_rc=0
  else
    grep_rc=$?
  fi
  (( grep_rc == 0 || grep_rc == 1 )) || return "$grep_rc"
}

gate_completed=false

write_final_status() {
  local rc="$1"
  local completed_utc="$2"
  {
    printf 'exit_status=%s\n' "$rc"
    printf 'started_utc=%s\n' "$started_utc"
    printf 'completed_utc=%s\n' "$completed_utc"
    printf 'early_failure=false\n'
    printf 'gate_completed=%s\n' "$gate_completed"
    printf 'kernel_reject_events_empty=%s\n' "$([[ ! -s "$evidence_root/kernel-reject-events.txt" ]] && printf true || printf false)"
  } > "$evidence_root/final-status.txt"
}

update_summary_finalization() {
  local passed="$1"
  local rc="$2"
  local completed_utc="$3"
  local reject_count=0
  if [[ -f "$evidence_root/kernel-reject-events.txt" ]]; then
    reject_count="$(wc -l < "$evidence_root/kernel-reject-events.txt")"
  fi
  jq --argjson passed "$passed" \
    --argjson exit_status "$rc" \
    --argjson kernel_reject_events "$reject_count" \
    --arg completed_utc "$completed_utc" '
      .passed = $passed |
      .gates.kernel_reject_events = $kernel_reject_events |
      .finalization = {
        passed: $passed,
        exit_status: $exit_status,
        completed_utc: $completed_utc,
        authoritative_final_kernel_capture: true
      }
    ' "$evidence_root/summary.json" > "$evidence_root/summary.json.final.tmp" \
    && mv "$evidence_root/summary.json.final.tmp" "$evidence_root/summary.json"
}

write_manifest() {
  (
    cd "$evidence_root" || exit 1
    find . -maxdepth 1 -type f ! -name 'evidence.sha256*' -printf '%P\n' \
      | LC_ALL=C sort \
      | xargs -r sha256sum \
      > evidence.sha256.tmp \
      && mv evidence.sha256.tmp evidence.sha256
  )
}

finalize() {
  local rc=$?
  local kernel_capture_rc=0
  local completed_utc
  local manifest_rc=0
  local sync_rc=0
  trap - EXIT
  set +e

  capture_kernel_delta
  kernel_capture_rc=$?
  if (( kernel_capture_rc != 0 && rc == 0 )); then
    rc=90
  fi
  if [[ -s "$evidence_root/kernel-reject-events.txt" && "$rc" -eq 0 ]]; then
    rc=91
  fi
  if [[ "$gate_completed" != true && "$rc" -eq 0 ]]; then
    rc=92
  fi

  completed_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [[ -f "$evidence_root/summary.json" ]]; then
    update_summary_finalization "$([[ "$rc" -eq 0 ]] && printf true || printf false)" \
      "$rc" "$completed_utc"
    if (( $? != 0 && rc == 0 )); then
      rc=93
      update_summary_finalization false "$rc" "$completed_utc"
    fi
  elif [[ "$gate_completed" == true && "$rc" -eq 0 ]]; then
    rc=93
  fi

  write_final_status "$rc" "$completed_utc"
  write_manifest
  manifest_rc=$?
  if (( manifest_rc != 0 )); then
    rc=94
    if [[ -f "$evidence_root/summary.json" ]]; then
      update_summary_finalization false "$rc" "$completed_utc"
    fi
    write_final_status "$rc" "$completed_utc"
    write_manifest
  fi

  sync "$evidence_root"
  sync_rc=$?
  if (( sync_rc != 0 )); then
    rc=95
    if [[ -f "$evidence_root/summary.json" ]]; then
      update_summary_finalization false "$rc" "$completed_utc"
    fi
    write_final_status "$rc" "$completed_utc"
    write_manifest
    sync "$evidence_root"
  fi

  if (( rc == 0 )); then
    echo "post-reboot recovery gate passed: $evidence_root"
  else
    echo "post-reboot recovery gate failed: status=$rc root=$evidence_root" >&2
  fi
  exit "$rc"
}
trap finalize EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

run_capture() {
  local label="$1"
  shift
  local rc
  set +e
  "$@" > "$evidence_root/$label.log" 2>&1
  rc=$?
  set -e
  printf 'exit_status=%s\n' "$rc" > "$evidence_root/$label.status"
  if (( rc != 0 )); then
    echo "$label failed with exit status $rc" >&2
    return "$rc"
  fi
}

capture_idle_xpu() {
  local output_path="$1"
  local residual_path="$2"
  timeout 15 xpu-smi ps > "$output_path"
  awk '
    NR == 1 {
      header_ok = $1 == "PID" && $2 == "Command" && $3 == "DeviceID" \
        && $4 == "SHR" && $5 == "MEM"
      next
    }
    {
      rows += 1
      if ($2 != "xpu-smi" || $3 !~ /^[0-3]$/) {
        print
        bad = 1
        next
      }
      seen[$3] += 1
    }
    END {
      if (!header_ok) {
        print "invalid xpu-smi ps header"
        bad = 1
      }
      if (rows != 4) {
        print "expected exactly four xpu-smi rows; found " rows
        bad = 1
      }
      for (device = 0; device < 4; device += 1) {
        if (seen[device] != 1) {
          print "expected one xpu-smi row for device " device "; found " seen[device]
          bad = 1
        }
      }
      exit bad
    }
  ' "$output_path" > "$residual_path"
}

require_no_model_process() {
  local output_path="$1"
  local rc
  if pgrep -af \
    '[g]emma4|[l]lama-server|[v]llm serve|[a]pi_server|[E]ngineCore' \
    > "$output_path"; then
    echo "model process remains active" >&2
    return 1
  else
    rc=$?
  fi
  (( rc == 1 ))
}

require_service_not_active() {
  local unit="$1"
  local state rc
  if state="$(systemctl is-active "$unit" 2>/dev/null)"; then
    rc=0
  else
    rc=$?
  fi
  printf '%s\t%s\trc=%s\n' "$unit" "$state" "$rc" \
    >> "$evidence_root/service-states.txt"
  (( rc == 3 )) && [[ "$state" == inactive || "$state" == failed ]]
}

require_no_model_ports() {
  local listeners_path="$1"
  local residual_path="$2"
  local rc
  ss -Hltn > "$listeners_path"
  if awk '
    $4 ~ /:(8000|18080|19350|19351|19352|19353)$/ {
      print
      found = 1
    }
    END { exit found ? 0 : 1 }
  ' "$listeners_path" > "$residual_path"; then
    echo "model-serving port is still listening" >&2
    return 1
  else
    rc=$?
  fi
  (( rc == 1 ))
}

check_hash() {
  local path="$1"
  local expected="$2"
  local actual
  actual="$(sha256sum "$path" | awk '{print $1}')"
  if [[ "$actual" != "$expected" ]]; then
    echo "hash mismatch: $path expected=$expected actual=$actual" >&2
    return 1
  fi
}

boot_id="$(< /proc/sys/kernel/random/boot_id)"
kernel_release="$(uname -r)"
kernel_taint="$(< /proc/sys/kernel/tainted)"
printf '%s\n' "$boot_id" > "$evidence_root/boot-id.txt"
printf '%s\n' "$kernel_release" > "$evidence_root/kernel-release.txt"
printf '%s\n' "$kernel_taint" > "$evidence_root/kernel-taint.txt"
uname -a > "$evidence_root/uname.txt"
[[ "$boot_id" == "$expected_boot_id" ]]
[[ "$boot_id" != "$tainted_ntfs_boot_id" ]]
[[ "$boot_id" != "$device_lost_boot_id" ]]
[[ "$kernel_release" == "$expected_kernel" ]]
[[ "$kernel_release" != "$device_lost_kernel" ]]
[[ "$kernel_taint" == 0 ]]

: > "$evidence_root/service-states.txt"
require_service_not_active gemma4-26b-q8-quad-frontdoor.service
require_service_not_active gemma4-26b-q8-quad-backends.service
require_service_not_active display-manager.service
require_no_model_process "$evidence_root/preflight-model-processes.txt"
require_no_model_ports \
  "$evidence_root/preflight-listeners.txt" \
  "$evidence_root/preflight-listener-residual.txt"

git -C "$repo_root" rev-parse HEAD > "$evidence_root/repo-head.txt"
git -C "$vllm_root" rev-parse HEAD > "$evidence_root/vllm-head.txt"
git -C "$kernel_root" rev-parse HEAD > "$evidence_root/kernel-head.txt"
git -C "$repo_root" status --short > "$evidence_root/repo-status.txt"
git -C "$vllm_root" status --short > "$evidence_root/vllm-status.txt"
git -C "$kernel_root" status --short > "$evidence_root/kernel-status.txt"
[[ ! -s "$evidence_root/repo-status.txt" ]]
[[ ! -s "$evidence_root/vllm-status.txt" ]]
[[ ! -s "$evidence_root/kernel-status.txt" ]]
[[ "$(< "$evidence_root/vllm-head.txt")" == "$expected_vllm_commit" ]]
[[ "$(< "$evidence_root/kernel-head.txt")" == "$expected_kernel_commit" ]]

sha256sum "$0" "$paths_script" "$oracle" "$base_gate" "$xccl_gate" \
  "$sycl_ls" "$umf_library" "$level_zero_adapter" "$level_zero_adapter_v2" \
  > "$evidence_root/tool-identities.sha256"
check_hash "$paths_script" "$expected_paths_script_sha256"
check_hash "$oracle" "$expected_oracle_sha256"
check_hash "$base_gate" "$expected_base_gate_sha256"
check_hash "$xccl_gate" "$expected_xccl_gate_sha256"
check_hash "$peer_binary" "$expected_peer_sha256"
check_hash "$sycl_ls" "$expected_sycl_ls_sha256"
check_hash "$umf_library" "$expected_umf_library_sha256"
check_hash "$level_zero_adapter" "$expected_level_zero_adapter_sha256"
check_hash "$level_zero_adapter_v2" "$expected_level_zero_adapter_v2_sha256"
printf '%s\n' "$oneapi_runtime_ld_library_path" \
  > "$evidence_root/oneapi-runtime-ld-library-path.txt"
printf '%s  %s\n' "$expected_peer_sha256" "$peer_binary" \
  > "$evidence_root/peer-binary.sha256"

check_hash "$LAGUNA_NVME_SOURCE_MANIFEST" "$expected_model_manifest_sha256"
check_hash "$LAGUNA_NVME_LOCAL_MANIFEST" "$expected_model_manifest_sha256"
cmp "$LAGUNA_NVME_SOURCE_MANIFEST" "$LAGUNA_NVME_LOCAL_MANIFEST"
run_capture model-content-manifest \
  timeout --signal=TERM --kill-after=15s 300s \
  bash -c '
    cd -- "$1"
    exec sha256sum -c -- .verification/nvme-files.sha256
  ' bash "$LAGUNA_NVME_MODEL_ROOT"
[[ "$(grep -c ': OK$' "$evidence_root/model-content-manifest.log")" == 118 ]]

run_capture xpu-smi-version timeout --signal=TERM --kill-after=5s 20s xpu-smi -v
run_capture xpu-smi-discovery \
  timeout --signal=TERM --kill-after=5s 20s xpu-smi discovery -j
jq -e '
  (.device_list | length == 4) and
  (.device_list[0] | .device_id == 0 and .pci_bdf_address == "0000:23:00.0" and .drm_device == "/dev/dri/card3" and .device_name == "Intel(R) Arc(TM) Pro B70 Graphics") and
  (.device_list[1] | .device_id == 1 and .pci_bdf_address == "0000:27:00.0" and .drm_device == "/dev/dri/card4" and .device_name == "Intel(R) Arc(TM) Pro B70 Graphics") and
  (.device_list[2] | .device_id == 2 and .pci_bdf_address == "0000:43:00.0" and .drm_device == "/dev/dri/card0" and .device_name == "Intel(R) Arc(TM) Pro B70 Graphics") and
  (.device_list[3] | .device_id == 3 and .pci_bdf_address == "0000:47:00.0" and .drm_device == "/dev/dri/card2" and .device_name == "Intel(R) Arc(TM) Pro B70 Graphics")
' "$evidence_root/xpu-smi-discovery.log" > "$evidence_root/xpu-mapping-check.txt"
capture_idle_xpu \
  "$evidence_root/preflight-xpu-ps.txt" \
  "$evidence_root/preflight-xpu-residual.txt"

run_capture sycl-ls-verbose \
  timeout --signal=TERM --kill-after=10s 60s \
  env -u UR_LOG_LOADER \
  LD_LIBRARY_PATH="$oneapi_runtime_ld_library_path" \
  "$sycl_ls" \
  --verbose --ignore-device-selectors
for rank in 0 1 2 3; do
  grep -Fq "[level_zero:gpu][level_zero:$rank]" \
    "$evidence_root/sycl-ls-verbose.log"
done

run_capture peer-read \
  timeout --signal=TERM --kill-after=15s 180s \
  env -u UR_LOG_LOADER \
  LD_LIBRARY_PATH="$oneapi_runtime_ld_library_path" \
  ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 \
  ZE_AFFINITY_MASK=0,1,2,3 \
  "$peer_binary"
[[ "$(< "$evidence_root/peer-read.log")" == "peer kernel read ok across 4 devices" ]]

run_xccl_pass() {
  local label="$1"
  local rank
  run_capture "$label" \
    timeout --signal=TERM --kill-after=15s 180s \
    env PYTHON="$python" ROOT="$repo_root" \
    PHYSICAL_DEVICES=0,1,2,3 XCCL_DEVICES=0,1,2,3 XCCL_NPROC=4 \
    TIMEOUT_S=120 FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1 \
    bash "$xccl_gate"
  [[ "$(awk '$0 == "device_count 1" {n++} END {print n+0}' "$evidence_root/$label.log")" == 4 ]]
  [[ "$(awk '$0 == "ok 2097152.0" {n++} END {print n+0}' "$evidence_root/$label.log")" == 4 ]]
  for rank in 0 1 2 3; do
    [[ "$(grep -Fxc "rank $rank init ok" "$evidence_root/$label.log")" == 1 ]]
    [[ "$(grep -Fxc "rank $rank barrier ok" "$evidence_root/$label.log")" == 1 ]]
    [[ "$(grep -Fxc "rank $rank allreduce ok 4.0" "$evidence_root/$label.log")" == 1 ]]
  done
}

run_xccl_pass xccl-pass-1
run_xccl_pass xccl-pass-2

for rank in 0 1 2 3; do
  run_capture "n64-oracle-card$rank" \
    timeout --signal=TERM --kill-after=15s 900s \
    env PYTHONPATH="$vllm_root:$kernel_root" \
    ZE_AFFINITY_MASK="$rank" ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    "$python" "$oracle" --rank "$rank" \
    --out "$evidence_root/n64-oracle-card$rank.json"
  jq -e '
    .passed == true and
    .oracle_gate_evaluated == true and
    .mode == "oracle-n64" and
    .executed_w1_n_tiles == [64] and
    .observed_w1_call_count == 128 and
    .n128_executed == false and
    ([.checks[]] | all)
  ' "$evidence_root/n64-oracle-card$rank.json" \
    > "$evidence_root/n64-oracle-card$rank.check"

  run_capture "n64-production-liveness-card$rank" \
    timeout --signal=TERM --kill-after=15s 300s \
    env PYTHONPATH="$vllm_root:$kernel_root" \
    ZE_AFFINITY_MASK="$rank" ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    "$python" "$base_gate" --rank "$rank" --mode counter-n64 \
    --out "$evidence_root/n64-production-liveness-card$rank.json"
  jq -e --argjson rank "$rank" \
    --arg fixture "$expected_fixture_sha256" \
    --arg extension "$expected_xpu_extension_sha256" \
    --arg grouped "$expected_grouped_gemm_sha256" '
    .passed == null and
    .counter_gate_evaluated == false and
    .counter.mode == "counter-n64" and
    .counter.rank == $rank and
    .counter.tile == 64 and
    .counter.calls == 12 and
    .counter.completion_boundary_per_call == true and
    .counter.real_production_fixture_identity.sha256 == $fixture and
    .runtime.extension_sha256 == $extension and
    .runtime.grouped_gemm_sha256 == $grouped
  ' "$evidence_root/n64-production-liveness-card$rank.json" \
    > "$evidence_root/n64-production-liveness-card$rank.check"
done

capture_kernel_delta
[[ ! -s "$evidence_root/kernel-reject-events.txt" ]]
require_no_model_process "$evidence_root/pre-idle-model-processes.txt"
capture_idle_xpu \
  "$evidence_root/pre-idle-xpu-ps.txt" \
  "$evidence_root/pre-idle-xpu-residual.txt"
idle_started_epoch="$(date +%s)"
idle_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' "$idle_started_utc" > "$evidence_root/idle-started-utc.txt"
: > "$evidence_root/idle-samples-xpu-ps.txt"
: > "$evidence_root/idle-samples-model-processes.txt"
idle_sample_count=0
while true; do
  idle_sample_count=$(( idle_sample_count + 1 ))
  sample_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  capture_idle_xpu \
    "$evidence_root/idle-current-xpu-ps.txt" \
    "$evidence_root/idle-current-xpu-residual.txt"
  require_no_model_process "$evidence_root/idle-current-model-processes.txt"
  {
    printf 'sample=%s utc=%s\n' "$idle_sample_count" "$sample_utc"
    cat "$evidence_root/idle-current-xpu-ps.txt"
  } >> "$evidence_root/idle-samples-xpu-ps.txt"
  printf 'sample=%s utc=%s no_model_process=true\n' \
    "$idle_sample_count" "$sample_utc" \
    >> "$evidence_root/idle-samples-model-processes.txt"
  sample_epoch="$(date +%s)"
  if (( sample_epoch - idle_started_epoch >= 65 )); then
    break
  fi
  sleep 1
done
idle_completed_epoch="$(date +%s)"
idle_completed_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
idle_seconds=$(( idle_completed_epoch - idle_started_epoch ))
printf '%s\n' "$idle_completed_utc" > "$evidence_root/idle-completed-utc.txt"
printf '%s\n' "$idle_seconds" > "$evidence_root/idle-seconds.txt"
printf '%s\n' "$idle_sample_count" > "$evidence_root/idle-sample-count.txt"
(( idle_seconds >= 65 ))
(( idle_sample_count >= 30 ))
require_no_model_process "$evidence_root/post-idle-model-processes.txt"
capture_idle_xpu \
  "$evidence_root/post-idle-xpu-ps.txt" \
  "$evidence_root/post-idle-xpu-residual.txt"
require_service_not_active gemma4-26b-q8-quad-frontdoor.service
require_service_not_active gemma4-26b-q8-quad-backends.service
require_service_not_active display-manager.service
require_no_model_ports \
  "$evidence_root/post-idle-listeners.txt" \
  "$evidence_root/post-idle-listener-residual.txt"
capture_kernel_delta
[[ ! -s "$evidence_root/kernel-reject-events.txt" ]]

jq -n \
  --arg boot_id "$boot_id" \
  --arg tainted_ntfs_boot_id "$tainted_ntfs_boot_id" \
  --arg device_lost_boot_id "$device_lost_boot_id" \
  --arg kernel_release "$kernel_release" \
  --arg device_lost_kernel "$device_lost_kernel" \
  --argjson kernel_taint "$kernel_taint" \
  --arg started_utc "$started_utc" \
  --arg idle_started_utc "$idle_started_utc" \
  --arg idle_completed_utc "$idle_completed_utc" \
  --argjson idle_seconds "$idle_seconds" \
  --argjson idle_sample_count "$idle_sample_count" \
  --arg repo_head "$(< "$evidence_root/repo-head.txt")" \
  --arg vllm_head "$(< "$evidence_root/vllm-head.txt")" \
  --arg kernel_head "$(< "$evidence_root/kernel-head.txt")" \
  --arg oneapi_runtime_ld_library_path "$oneapi_runtime_ld_library_path" '
  {
    format: "laguna-w1-n128-postreboot-recovery-v1",
    passed: true,
    boot: {
      boot_id: $boot_id,
      differs_from_tainted_ntfs_boot_id: ($boot_id != $tainted_ntfs_boot_id),
      differs_from_device_lost_boot_id: ($boot_id != $device_lost_boot_id),
      kernel_release: $kernel_release,
      differs_from_device_lost_kernel: ($kernel_release != $device_lost_kernel),
      kernel_taint: $kernel_taint
    },
    source_identity: {
      repo_head: $repo_head,
      vllm_head: $vllm_head,
      kernel_head: $kernel_head,
      trees_clean: true
    },
    runtime_identity: {
      oneapi_runtime_ld_library_path: $oneapi_runtime_ld_library_path,
      runtime_files_hash_pinned: true
    },
    gates: {
      exact_four_device_mapping: true,
      local_nvme_ext4_evidence_root: true,
      local_model_manifest_files_verified: 118,
      strict_gpu_idle_before_gates: true,
      oneapi_2026_four_device_enumeration: true,
      four_device_peer_read: true,
      xccl_exact_allreduce_independent_passes: 2,
      n64_historical_exact_oracle_cards: 4,
      n64_production_fixture_liveness_cards: 4,
      n128_executed: false,
      model_generation_performed: false,
      kernel_reject_events: 0
    },
    idle: {
      started_utc: $idle_started_utc,
      completed_utc: $idle_completed_utc,
      seconds: $idle_seconds,
      required_seconds: 65,
      strict_samples: $idle_sample_count,
      minimum_strict_samples: 30,
      no_device_or_model_client_detected: true,
      services_and_ports_rechecked_after_interval: true
    },
    campaign_constraints: {
      recovery_a1_must_be_first_post_recovery_model_generation: true,
      one_prior_invalid_aborted_control_start_disclosed: true,
      all_recovery_preflight_aborts_disclosed: true,
      no_performance_conditioned_campaign_retry: true
    },
    started_utc: $started_utc
  }
' > "$evidence_root/summary.json.tmp"
mv "$evidence_root/summary.json.tmp" "$evidence_root/summary.json"
sync "$evidence_root/summary.json"

gate_completed=true
