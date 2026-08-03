#!/bin/bash
# One fresh post-recovery exact-small non-scored smoke. A scored endpoint needs
# a separate post-smoke preregistration and execution lock.
set -euo pipefail
umask 077

readonly wrapper_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
if [[ "${LAGUNA_EXACT_SMALL_CLEAN_ENV:-0}" != 1 ]]; then
  exec /usr/bin/env -i \
    PATH="$wrapper_path" HOME=/home/steve LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    LAGUNA_EXACT_SMALL_CLEAN_ENV=1 /usr/bin/bash "$0" "$@"
fi
while IFS= read -r env_name; do
  case "$env_name" in
    HOME|LAGUNA_EXACT_SMALL_CLEAN_ENV|LANG|LC_ALL|PATH|PWD|SHLVL) ;;
    *) echo "unexpected coordinator environment variable: $env_name" >&2; exit 2 ;;
  esac
done < <(compgen -e)
export PATH="$wrapper_path" HOME=/home/steve LANG=C.UTF-8 LC_ALL=C.UTF-8

tag="${1:?usage: run_laguna_exact_small_postrecovery.sh TAG}"
(( $# == 1 )) || { echo "exactly one tag is required" >&2; exit 2; }
[[ "$tag" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$ ]] \
  || { echo "invalid tag" >&2; exit 2; }

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

readonly runner="$script_dir/run_laguna_replemb_measurement_leg.sh"
readonly lock="$script_dir/exact-small-postrecovery-lock.json"
readonly recovery_packet="$repo_root/data/laguna-device-recovery-scheduler-gate-20260802.json"
readonly runtime_lock="$repo_root/data/laguna-exact-small-portfolio-runtime-lock-20260801.json"
readonly vllm_tree=/home/steve/src/laguna-vllm-exact-small-portfolio-20260801
readonly kernel_tree=/home/steve/src/laguna-xpu-kernels-exact-small-portfolio-20260801
readonly grouped_route_source="$kernel_tree/csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp"
readonly vllm_commit=0c9dea8cf9aa46c1854d5bce8f4dfb180732b16d
readonly kernel_commit=46a6393fc188c11661ddab9cf1320d2f3de45087
readonly runtime_lock_sha=42e50b479b9ecc31db63998cd1b7bfe5cb7865ee38ed80516232bc9428765836
readonly native_c_sha=36d97dda1438cd06b5f707859edb2a0960fd05d09ef6c6d29a53aa89cdd04095
readonly moe_c_sha=51a1f2b02fc8a21e420edfff79c30ff0f2170d4bab0b6b1efb25d1f79b1f8a66
readonly grouped_gemm_sha=5d2d29e63f40c62d31b61808d74a0ef7ba71f2c6a62754c3220ed4d0c8281d4b
readonly runs=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs
readonly campaign_root="$runs/laguna-exact-small-postrecovery-$tag-campaign"
readonly smoke_run="$runs/laguna-exact-small-postrecovery-$tag-smoke"
readonly smoke_rpc_dir="$LAGUNA_NVME_TMP_ROOT/m8mc-b1"
readonly device_error_regex='guc.*(timeout|reset|error)|exec.*queue.*timeout|wedg|gpu.*(hang|reset|fault)|xe.*(timeout|reset|error|fail|fault|hang)|drm.*(timeout|reset|error|fail|fault|hang)'
readonly mem_available_floor_kb=8388608
readonly combined_mem_floor_kb=16777216
readonly combined_swap_floor_kb=4194304
active_leg_pid=""

die() { echo "Laguna exact-small post-recovery gate: $*" >&2; exit 2; }
sha256() { sha256sum -- "$1" | awk '{print $1}'; }

[[ -f "$lock" && -f "$recovery_packet" && -f "$runtime_lock" ]] \
  || die "missing execution evidence or lock"
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main repository is dirty"
[[ "$(jq -r .schema "$lock")" == laguna-exact-small-postrecovery-execution-lock-v1 \
   && "$(jq -r .status "$lock")" == PASS ]] || die "execution lock is not PASS"

required_lock_files=(
  CURRENT.md
  data/laguna-device-recovery-scheduler-gate-20260802.json
  data/laguna-exact-small-portfolio-component-20260801.json
  data/laguna-exact-small-portfolio-runtime-lock-20260801.json
  data/laguna-shared-elementwise-m12-record-20260731.json
  experiments/laguna-s-2.1-xpu-b70/RESUME.md
  experiments/laguna-s-2.1-xpu-b70/notes/2026-08-01-exact-small-component-portfolio-preregistration.md
  experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-exact-small-postrecovery-preregistration.md
  experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json
  experiments/laguna-s-2.1-xpu-b70/tools/capture_laguna_m8_idle_snapshot.py
  experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py
  experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh
  experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_dflash_segmented_smoke.py
  experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_exact_small_postrecovery.sh
  experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_replemb_measurement_leg.sh
  experiments/laguna-s-2.1-xpu-b70/tools/serve_laguna_mwide_graph_nvme.sh
  experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_exact_small_postrecovery.py
  repro/laguna-s-2.1-int4-b70-102tps-20260726/manifests/model-release-files.sha256
  repro/laguna-s-2.1-int4-b70-102tps-20260726/verify-runtime.py
  scripts/bench-openai-realistic-suite.py
  scripts/qualify_realistic_window_metrics.py
)
observed_lock_files="$(jq -r '.files | if type == "object" then keys[] else error("files is not an object") end' "$lock")"
expected_lock_files="$(printf '%s\n' "${required_lock_files[@]}" | LC_ALL=C sort)"
[[ "$observed_lock_files" == "$expected_lock_files" ]] \
  || die "execution lock file set mismatch"
while IFS=$'\t' read -r relative expected_sha; do
  [[ "$(sha256 "$repo_root/$relative")" == "$expected_sha" ]] \
    || die "execution lock hash mismatch: $relative"
done < <(jq -r '.files | to_entries[] | [.key, .value] | @tsv' "$lock")

lock_relative="${lock#"$repo_root/"}"
lock_commit="$(git -C "$repo_root" log -1 --format=%H -- "$lock")"
[[ "$(git -C "$repo_root" rev-parse HEAD)" == "$lock_commit" ]] \
  || die "execution lock must be the repository HEAD"
[[ "$(git -C "$repo_root" diff-tree --no-commit-id --name-only -r "$lock_commit")" == "$lock_relative" ]] \
  || die "execution-lock commit changed more than the lock"
[[ "$(git -C "$repo_root" rev-parse "$lock_commit^")" == "$(jq -r .harness_commit "$lock")" ]] \
  || die "execution lock is not bound to its harness commit"
[[ "$tag" == "$(jq -r .authorized.tag "$lock")" \
   && "$campaign_root" == "$(jq -r .authorized.campaign_root "$lock")" \
   && "$smoke_run" == "$(jq -r .authorized.smoke_root "$lock")" ]] \
  || die "tag or run roots differ from the one-shot authorization"
git_common_dir="$(git -C "$repo_root" rev-parse --git-common-dir)"
[[ "$git_common_dir" == /* ]] || git_common_dir="$repo_root/$git_common_dir"
readonly campaign_mutex="$git_common_dir/laguna-exact-small-postrecovery.lock"
exec 9>>"$campaign_mutex"
flock -n 9 || die "another exact-small campaign holds the stable mutex"
[[ "$(jq -r .source_commits.vllm "$lock")" == "$vllm_commit" \
   && "$(jq -r .source_commits.kernel "$lock")" == "$kernel_commit" ]] \
  || die "execution lock source commit mismatch"
[[ "$(jq -r .runtime_lock_sha256 "$lock")" == "$runtime_lock_sha" \
   && "$(sha256 "$runtime_lock")" == "$runtime_lock_sha" ]] \
  || die "runtime lock mismatch"
[[ "$(jq -r .native_hashes._C "$lock")" == "$native_c_sha" \
   && "$(jq -r .native_hashes._moe_C "$lock")" == "$moe_c_sha" \
   && "$(jq -r .native_hashes.grouped_gemm "$lock")" == "$grouped_gemm_sha" ]] \
  || die "execution lock native hash mismatch"
[[ "$(sha256 "$grouped_route_source")" == "$(jq -r .static_route_sha256 "$lock")" ]] \
  || die "exact-small static route source hash mismatch"

[[ -z "$(git -C "$vllm_tree" status --short)" \
   && "$(git -C "$vllm_tree" rev-parse HEAD)" == "$vllm_commit" ]] \
  || die "frozen vLLM tree mismatch"
[[ -z "$(git -C "$kernel_tree" status --short)" \
   && "$(git -C "$kernel_tree" rev-parse HEAD)" == "$kernel_commit" ]] \
  || die "frozen kernel tree mismatch"
[[ "$(sha256 "$kernel_tree/vllm_xpu_kernels/_C.abi3.so")" == "$native_c_sha" \
   && "$(sha256 "$kernel_tree/vllm_xpu_kernels/_moe_C.abi3.so")" == "$moe_c_sha" \
   && "$(sha256 "$kernel_tree/vllm_xpu_kernels/libgrouped_gemm_xe_2.so")" == "$grouped_gemm_sha" ]] \
  || die "candidate native binary drift"

[[ "$(jq -r .status "$recovery_packet")" == PASS ]] \
  || die "recovery packet is not PASS"
expected_boot_id="$(jq -r .boot.after_id "$recovery_packet")"
[[ "$(</proc/sys/kernel/random/boot_id)" == "$expected_boot_id" ]] \
  || die "current boot differs from passed recovery boot"
[[ "$(sha256 "$recovery_packet")" == "$(jq -r .recovery_packet_sha256 "$lock")" ]] \
  || die "recovery evidence packet hash mismatch"
recovery_root="$(jq -r .artifact_root "$recovery_packet")"
[[ -d "$recovery_root" && -f "$recovery_root/manifest.sha256" \
   && -z "$(find "$recovery_root" -perm /222 -print -quit)" ]] \
  || die "sealed recovery root is missing or writable"
(cd "$recovery_root" && sha256sum -c manifest.sha256 >/dev/null) \
  || die "recovery manifest verification failed"
recovery_completed_raw="$(jq -r .completed_at_utc "$recovery_root/summary.json")"
[[ "$recovery_completed_raw" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|\+00:00)$ ]] \
  || die "recovery completion timestamp is malformed"
readonly journal_since_utc="$(date -u -d "$recovery_completed_raw" +%Y-%m-%dT%H:%M:%SZ)"

device_specs=(
  '0000:23:00.0|card3|controlD67|renderD130'
  '0000:27:00.0|card4|controlD68|renderD131'
  '0000:43:00.0|card0|controlD64|renderD128'
  '0000:47:00.0|card2|controlD66|renderD129'
)
drm_paths=()
for spec in "${device_specs[@]}"; do
  IFS='|' read -r bdf card control render <<< "$spec"
  drm_paths+=("/dev/dri/$card" "/dev/dri/$render")
done

capture_host_snapshot() {
  local phase="$1"
  {
    printf 'captured_at_utc=%s\nboot_id=%s\nkernel=%s\ntaint=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(</proc/sys/kernel/random/boot_id)" \
      "$(uname -r)" "$(</proc/sys/kernel/tainted)"
    awk '/^(MemAvailable|SwapFree|SwapTotal):/ {print}' /proc/meminfo
    awk 'NR > 1 {print "swap=" $1 ":" $3}' /proc/swaps | LC_ALL=C sort
  } > "$campaign_root/host-${phase}.txt"
}

verify_host_idle() {
  local phase="$1" observed_swap process_status listener_status fuser_status
  local mem_available_kb swap_free_kb unit state spec bdf card control render
  local device_dir observed_drm expected_drm
  capture_host_snapshot "$phase"
  [[ "$(</proc/sys/kernel/random/boot_id)" == "$expected_boot_id" ]] \
    || die "boot changed during campaign"
  [[ "$(uname -r)" == "$(jq -r .boot.kernel "$recovery_packet")" \
     && "$(</proc/sys/kernel/tainted)" == 0 ]] \
    || die "kernel identity or taint failed at $phase"
  set +e
  pgrep -af 'vllm serve|VLLM::EngineCore|VLLM::Worker|torchrun' \
    > "$campaign_root/processes-${phase}.txt" 2> "$campaign_root/processes-${phase}.stderr"
  process_status=$?
  ss -H -ltn 'sport = :8000 or sport = :18080' \
    > "$campaign_root/listeners-${phase}.txt" 2> "$campaign_root/listeners-${phase}.stderr"
  listener_status=$?
  fuser "${drm_paths[@]}" > "$campaign_root/drm-openers-${phase}.txt" \
    2> "$campaign_root/drm-openers-${phase}.stderr"
  fuser_status=$?
  set -e
  (( process_status == 1 )) && [[ ! -s "$campaign_root/processes-${phase}.stderr" ]] \
    || die "model process check failed or matched at $phase"
  (( listener_status == 0 )) && [[ ! -s "$campaign_root/listeners-${phase}.stderr" ]] \
    || die "listener inspection failed at $phase"
  [[ ! -s "$campaign_root/listeners-${phase}.txt" ]] \
    || die "protected listener survives at $phase"
  (( fuser_status == 1 )) && [[ ! -s "$campaign_root/drm-openers-${phase}.stderr" ]] \
    || die "DRM opener check failed or matched at $phase"
  for unit in gemma4-26b-q8-quad-backends.service gemma4-26b-q8-quad-frontdoor.service; do
    state="$(systemctl is-active "$unit" 2>&1 || true)"
    printf '%s=%s\n' "$unit" "$state" >> "$campaign_root/units-${phase}.txt"
    [[ "$state" == inactive ]] \
      || die "$unit is not exactly inactive at $phase"
  done
  observed_swap="$(awk 'NR > 1 {print $1 ":" $3}' /proc/swaps | LC_ALL=C sort)"
  [[ "$observed_swap" == /swap.img:8388604 \
     && ! -e /swap-laguna-longctx.img ]] \
    || die "ordinary 8 GiB swap layout drift at $phase"
  [[ ! -e "$smoke_rpc_dir" && ! -L "$smoke_rpc_dir" ]] \
    || die "smoke RPC path survives at $phase"
  ip -o -4 addr show dev eno1 | grep -Eq 'inet 10\.0\.0\.65/' \
    || die "frozen collective interface eno1/10.0.0.65 is unavailable"
  [[ "$(</sys/class/net/eno1/operstate)" == up ]] \
    || die "frozen collective interface eno1 is not up"
  mem_available_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  swap_free_kb="$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)"
  (( mem_available_kb >= mem_available_floor_kb \
      && (mem_available_kb >= combined_mem_floor_kb \
          || swap_free_kb >= combined_swap_floor_kb) )) \
    || die "frozen memory guard fails at $phase"
  : > "$campaign_root/device-identities-${phase}.txt"
  for spec in "${device_specs[@]}"; do
    IFS='|' read -r bdf card control render <<< "$spec"
    device_dir="/sys/bus/pci/devices/$bdf"
    [[ -d "$device_dir" \
       && "$(<"$device_dir/vendor")" == 0x8086 \
       && "$(<"$device_dir/device")" == 0xe223 \
       && "$(readlink -f "$device_dir/driver")" == /sys/bus/pci/drivers/xe \
       && "$(readlink -f "/sys/class/drm/$card/device")" == "$(readlink -f "$device_dir")" ]] \
      || die "device binding drift at $phase: $bdf"
    observed_drm="$(find "$device_dir/drm" -mindepth 1 -maxdepth 1 -printf '%f\n' | LC_ALL=C sort | paste -sd, -)"
    expected_drm="$(printf '%s\n' "$card" "$control" "$render" | LC_ALL=C sort | paste -sd, -)"
    [[ "$observed_drm" == "$expected_drm" ]] \
      || die "DRM node set drift at $phase: $bdf"
    [[ -c "/dev/dri/$card" && -c "/dev/dri/$render" ]] \
      || die "DRM character device missing at $phase: $bdf"
    printf '%s vendor=0x8086 device=0xe223 driver=xe drm=%s\n' \
      "$bdf" "$observed_drm" >> "$campaign_root/device-identities-${phase}.txt"
  done
}

scan_device_journal() {
  local phase="$1" grep_status
  journalctl -k -b --since "$journal_since_utc" --no-pager \
    > "$campaign_root/kernel-journal-${phase}.log"
  set +e
  grep -Eai "$device_error_regex" "$campaign_root/kernel-journal-${phase}.log" \
    > "$campaign_root/device-error-scan-${phase}.log" \
    2> "$campaign_root/device-error-scan-${phase}.stderr"
  grep_status=$?
  set -e
  [[ -f "$campaign_root/device-error-scan-${phase}.log" \
     && -f "$campaign_root/device-error-scan-${phase}.stderr" \
     && ! -s "$campaign_root/device-error-scan-${phase}.stderr" ]] \
    || die "device error scan inspection failed at $phase"
  if (( grep_status == 0 )); then
    die "device error detected at $phase"
  fi
  (( grep_status == 1 )) \
    || die "device error scan failed with status $grep_status at $phase"
}

build_leg_args() {
  local label="$1" run_dir="$2" smoke="$3"
  leg_args=(
    candidate "$label" "$run_dir"
    12 11 1 0 0 1 0 0 0 1 1 0 0 '' 64 1 ''
    6 0 1 0 0 1 "$smoke" 0.90 0 0 0 1 0 1 1 0 0 0 1
    0 '' 96 -1 0 0 0 1 1 1
  )
  (( ${#leg_args[@]} == 49 )) || die "internal leg argument count drift"
  [[ "${leg_args[3]}" == 12 && "${leg_args[4]}" == 11 \
     && "${leg_args[18]}" == 1 \
     && "${leg_args[21]}" == 0 && "${leg_args[22]}" == 1 \
     && "${leg_args[23]}" == 0 && "${leg_args[25]}" == 1 \
     && "${leg_args[26]}" == "$smoke" && "${leg_args[33]}" == 1 \
     && "${leg_args[34]}" == 1 && "${leg_args[38]}" == 1 \
     && "${leg_args[46]}" == 1 && "${leg_args[47]}" == 1 \
     && "${leg_args[48]}" == 1 ]] || die "internal leg identity drift"
}

stop_runner_bounded() {
  local pid="$1" status
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 60); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid" 2>/dev/null || true
  fi
  wait "$pid" 2>/dev/null
  status=$?
  return "$status"
}

cleanup_recorded_service() {
  local pid signal attempts
  local pid_file="$smoke_run/server.pid"
  [[ -f "$pid_file" ]] || return 0
  pid="$(<"$pid_file")"
  [[ "$pid" =~ ^[1-9][0-9]*$ ]] || return 1
  if kill -0 "$pid" 2>/dev/null; then
    tr '\0' ' ' < "/proc/$pid/cmdline" \
      > "$campaign_root/terminal-service-cmdline.txt" 2>/dev/null || return 1
    grep -Eq 'vllm|serve_laguna_mwide_graph_nvme' \
      "$campaign_root/terminal-service-cmdline.txt" || return 1
  elif ! kill -0 -- -"$pid" 2>/dev/null; then
    return 0
  fi
  for signal in INT TERM KILL; do
    kill -"$signal" -- -"$pid" 2>/dev/null || true
    kill -"$signal" "$pid" 2>/dev/null || true
    case "$signal" in INT) attempts=20 ;; TERM) attempts=10 ;; KILL) attempts=5 ;; esac
    for _ in $(seq 1 "$attempts"); do
      if ! kill -0 "$pid" 2>/dev/null \
         && ! kill -0 -- -"$pid" 2>/dev/null; then
        return 0
      fi
      sleep 1
    done
  done
  ! kill -0 "$pid" 2>/dev/null && ! kill -0 -- -"$pid" 2>/dev/null
}

verify_no_worker_survivors() {
  local worker_status
  pgrep -af 'VLLM::EngineCore|VLLM::Worker' \
    > "$campaign_root/terminal-surviving-workers.txt" \
    2> "$campaign_root/terminal-surviving-workers.stderr"
  worker_status=$?
  [[ "$worker_status" == 1 \
     && ! -s "$campaign_root/terminal-surviving-workers.stderr" ]]
}

terminal_audit() {
  local audit_status=0 process_status listener_status fuser_status journal_status
  local journal_grep_status
  local observed_swap unit state mem_available_kb swap_free_kb interface_status
  local spec bdf card control render device_dir observed_drm expected_drm
  capture_host_snapshot terminal
  (( $? == 0 )) || audit_status=1
  pgrep -af 'vllm serve|VLLM::EngineCore|VLLM::Worker|torchrun' \
    > "$campaign_root/processes-terminal.txt" 2> "$campaign_root/processes-terminal.stderr"
  process_status=$?
  ss -H -ltn 'sport = :8000 or sport = :18080' \
    > "$campaign_root/listeners-terminal.txt" 2> "$campaign_root/listeners-terminal.stderr"
  listener_status=$?
  fuser "${drm_paths[@]}" > "$campaign_root/drm-openers-terminal.txt" \
    2> "$campaign_root/drm-openers-terminal.stderr"
  fuser_status=$?
  journalctl -k -b --since "$journal_since_utc" --no-pager \
    > "$campaign_root/kernel-journal-terminal.log"
  journal_status=$?
  grep -Eai "$device_error_regex" "$campaign_root/kernel-journal-terminal.log" \
    > "$campaign_root/device-error-scan-terminal.log" \
    2> "$campaign_root/device-error-scan-terminal.stderr"
  journal_grep_status=$?
  observed_swap="$(awk 'NR > 1 {print $1 ":" $3}' /proc/swaps | LC_ALL=C sort)"
  : > "$campaign_root/units-terminal.txt"
  for unit in gemma4-26b-q8-quad-backends.service gemma4-26b-q8-quad-frontdoor.service; do
    state="$(systemctl is-active "$unit" 2>&1 || true)"
    printf '%s=%s\n' "$unit" "$state" >> "$campaign_root/units-terminal.txt"
    [[ "$state" == inactive ]] || audit_status=1
  done
  (( process_status == 1 )) \
    && [[ ! -s "$campaign_root/processes-terminal.stderr" ]] \
    || audit_status=1
  (( listener_status == 0 )) \
    && [[ ! -s "$campaign_root/listeners-terminal.stderr" ]] \
    || audit_status=1
  [[ ! -s "$campaign_root/listeners-terminal.txt" ]] || audit_status=1
  (( fuser_status == 1 )) \
    && [[ ! -s "$campaign_root/drm-openers-terminal.stderr" ]] \
    || audit_status=1
  (( journal_status == 0 )) || audit_status=1
  (( journal_grep_status == 1 )) \
    && [[ -f "$campaign_root/device-error-scan-terminal.log" \
          && -f "$campaign_root/device-error-scan-terminal.stderr" \
          && ! -s "$campaign_root/device-error-scan-terminal.stderr" ]] \
    || audit_status=1
  [[ ! -s "$campaign_root/device-error-scan-terminal.log" ]] || audit_status=1
  [[ "$(</proc/sys/kernel/random/boot_id)" == "$expected_boot_id" \
     && "$(</proc/sys/kernel/tainted)" == 0 ]] || audit_status=1
  [[ "$observed_swap" == /swap.img:8388604 \
     && ! -e /swap-laguna-longctx.img ]] || audit_status=1
  [[ ! -e "$smoke_rpc_dir" && ! -L "$smoke_rpc_dir" ]] || audit_status=1
  ip -o -4 addr show dev eno1 > "$campaign_root/interface-terminal.txt" 2>&1
  interface_status=$?
  [[ "$interface_status" == 0 && "$(</sys/class/net/eno1/operstate)" == up ]] \
    || audit_status=1
  grep -Eq 'inet 10\.0\.0\.65/' "$campaign_root/interface-terminal.txt" \
    || audit_status=1
  mem_available_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  swap_free_kb="$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)"
  (( mem_available_kb >= mem_available_floor_kb \
      && (mem_available_kb >= combined_mem_floor_kb \
          || swap_free_kb >= combined_swap_floor_kb) )) \
    || audit_status=1
  : > "$campaign_root/device-identities-terminal.txt"
  for spec in "${device_specs[@]}"; do
    IFS='|' read -r bdf card control render <<< "$spec"
    device_dir="/sys/bus/pci/devices/$bdf"
    if [[ ! -d "$device_dir" \
       || "$(<"$device_dir/vendor")" != 0x8086 \
       || "$(<"$device_dir/device")" != 0xe223 \
       || "$(readlink -f "$device_dir/driver")" != /sys/bus/pci/drivers/xe \
       || "$(readlink -f "/sys/class/drm/$card/device")" != "$(readlink -f "$device_dir")" ]]; then
      audit_status=1
      continue
    fi
    observed_drm="$(find "$device_dir/drm" -mindepth 1 -maxdepth 1 -printf '%f\n' | LC_ALL=C sort | paste -sd, -)"
    expected_drm="$(printf '%s\n' "$card" "$control" "$render" | LC_ALL=C sort | paste -sd, -)"
    [[ "$observed_drm" == "$expected_drm" ]] || audit_status=1
    [[ -c "/dev/dri/$card" && -c "/dev/dri/$render" ]] || audit_status=1
    printf '%s vendor=0x8086 device=0xe223 driver=xe drm=%s\n' \
      "$bdf" "$observed_drm" >> "$campaign_root/device-identities-terminal.txt"
  done
  printf 'status=%s\nprocess_status=%s\nlistener_status=%s\nfuser_status=%s\njournal_status=%s\njournal_grep_status=%s\n' \
    "$audit_status" "$process_status" "$listener_status" "$fuser_status" \
    "$journal_status" "$journal_grep_status" > "$campaign_root/terminal-audit.txt"
  return "$audit_status"
}

run_leg() {
  local phase="$1" label="$2" run_dir="$3" smoke="$4"
  local leg_pid leg_status mem_available_kb swap_free_kb memory_alarm=0
  build_leg_args "$label" "$run_dir" "$smoke"
  printf '%s\n' "${leg_args[@]}" | nl -ba > "$campaign_root/${phase}-arguments.txt"
  : > "$campaign_root/${phase}-memory-guard.tsv"
  : > "$campaign_root/${phase}.stdout"
  /usr/bin/env -i \
    PATH=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    HOME=/home/steve \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    REPRO_VLLM_TREE="$vllm_tree" \
    REPRO_KERNEL_TREE="$kernel_tree" \
    REPRO_RUNTIME_LOCK="$runtime_lock" \
    REPRO_RUNTIME_LOCK_SHA256="$runtime_lock_sha" \
    REPRO_NATIVE_C_SHA256="$native_c_sha" \
    REPRO_MOE_C_SHA256="$moe_c_sha" \
    REPRO_GROUPED_GEMM_SHA256="$grouped_gemm_sha" \
    REPRO_CLUSTER_IP=10.0.0.65 \
    "$runner" "${leg_args[@]}" > "$campaign_root/${phase}.stdout" 2>&1 &
  leg_pid=$!
  active_leg_pid="$leg_pid"
  while kill -0 "$leg_pid" 2>/dev/null; do
    mem_available_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
    swap_free_kb="$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)"
    printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      "$mem_available_kb" "$swap_free_kb" \
      >> "$campaign_root/${phase}-memory-guard.tsv"
    if (( mem_available_kb < mem_available_floor_kb \
          || (mem_available_kb < combined_mem_floor_kb \
              && swap_free_kb < combined_swap_floor_kb) )); then
      printf 'phase=%s mem_available_kb=%s swap_free_kb=%s\n' \
        "$phase" "$mem_available_kb" "$swap_free_kb" \
        > "$campaign_root/${phase}-memory-guard-alarm.txt"
      memory_alarm=1
      break
    fi
    sleep 1
  done
  if (( memory_alarm == 1 )); then
    set +e
    stop_runner_bounded "$leg_pid"
    leg_status=$?
    set -e
  else
    set +e
    wait "$leg_pid"
    leg_status=$?
    set -e
  fi
  active_leg_pid=""
  if (( memory_alarm == 1 )); then
    die "$phase crossed the frozen memory guard"
  fi
  (( leg_status == 0 )) || die "$phase failed with status $leg_status"
}

campaign_created=false
finalize_campaign() {
  local status="$?" cleanup_status=0 audit_status=0 seal_status=0
  local writable_entries find_status
  trap - EXIT INT TERM
  set +e
  if [[ -n "$active_leg_pid" ]] && kill -0 "$active_leg_pid" 2>/dev/null; then
    stop_runner_bounded "$active_leg_pid"
    active_leg_pid=""
  fi
  if [[ "$campaign_created" == true ]]; then
    cleanup_recorded_service || cleanup_status=1
    verify_no_worker_survivors || cleanup_status=1
    terminal_audit || audit_status=1
    (( status != 0 || (cleanup_status == 0 && audit_status == 0) )) || status=1
    printf 'exit_status=%s\ncleanup_status=%s\nterminal_audit_status=%s\nseal_status=0\ncompleted_at_utc=%s\n' \
      "$status" "$cleanup_status" "$audit_status" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$campaign_root/wrapper-status.txt" \
      || { status=1; seal_status=1; }
    if [[ -d "$smoke_run" ]]; then
      chmod -R a-w -- "$smoke_run" 2>/dev/null || seal_status=1
      writable_entries="$(find "$smoke_run" -perm /222 -print -quit 2>/dev/null)"
      find_status=$?
      [[ "$find_status" == 0 && -z "$writable_entries" ]] || seal_status=1
    fi
    chmod -R a-w -- "$campaign_root" 2>/dev/null || seal_status=1
    writable_entries="$(find "$campaign_root" -perm /222 -print -quit 2>/dev/null)"
    find_status=$?
    [[ "$find_status" == 0 && -z "$writable_entries" ]] || seal_status=1
    if (( seal_status != 0 )); then
      status=1
      chmod u+w -- "$campaign_root" "$campaign_root/wrapper-status.txt" \
        2>/dev/null || true
      printf 'exit_status=%s\ncleanup_status=%s\nterminal_audit_status=%s\nseal_status=%s\ncompleted_at_utc=%s\n' \
        "$status" "$cleanup_status" "$audit_status" "$seal_status" \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$campaign_root/wrapper-status.txt" \
        2>/dev/null || true
      chmod -R a-w -- "$campaign_root" 2>/dev/null || true
    fi
  fi
  exit "$status"
}
trap finalize_campaign EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for path in "$campaign_root" "$smoke_run"; do
  [[ ! -e "$path" && ! -L "$path" ]] || die "refusing reused path: $path"
done
campaign_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -m 700 "$campaign_root"
campaign_created=true

printf 'schema=laguna-exact-small-postrecovery-smoke-campaign-v1\ntag=%s\nstarted_at_utc=%s\nrepo_head=%s\nlock_commit=%s\nlock_sha256=%s\nrecovery_boot_id=%s\nsmoke_run=%s\n' \
  "$tag" "$campaign_started_utc" "$(git -C "$repo_root" rev-parse HEAD)" \
  "$lock_commit" "$(sha256 "$lock")" "$expected_boot_id" "$smoke_run" \
  > "$campaign_root/identity.txt"

verify_host_idle prestart
scan_device_journal prestart
laguna_nvme_prepare_paths
laguna_nvme_verify_model_contents > "$campaign_root/model-content-verification.log" 2>&1
printf 'PASS\n' > "$campaign_root/model-content-verification.status"

run_leg smoke B1 "$smoke_run" 1
verify_host_idle postsmoke
scan_device_journal postsmoke
[[ "$(awk -F= '$1 == "status" {print $2}' "$smoke_run/status.txt")" == PASS \
   && "$(awk -F= '$1 == "scored_measurement" {print $2}' "$smoke_run/status.txt")" == false ]] \
  || die "non-scored smoke did not pass"
printf 'SMOKE_PASS\n' > "$campaign_root/status.txt"

echo "Laguna exact-small post-recovery smoke complete: $campaign_root"
