#!/usr/bin/env bash
# Run the frozen scheduler-budget control A followed by candidate B exactly once.
set -euo pipefail
umask 077

tag="${1:?usage: run_laguna_scheduler_alignment_pair.sh TAG REPEAT_ORACLE}"
oracle="${2:?usage: run_laguna_scheduler_alignment_pair.sh TAG REPEAT_ORACLE}"
[[ "$tag" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$ ]] || {
  echo "invalid tag" >&2
  exit 2
}
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"
runner="$script_dir/run_laguna_long_context_baseline.sh"
analyzer="$script_dir/analyze_laguna_scheduler_alignment.py"
python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
lock="$script_dir/scheduler-alignment-lock.json"
recovery_packet="$repo_root/data/laguna-device-recovery-scheduler-gate-20260802.json"
expected_oracle="$repo_root/data/laguna-scheduler-alignment-repeat-oracle-20260802.json"
oracle="$(realpath -- "$oracle")"
[[ "$oracle" == "$expected_oracle" ]] || { echo "repeat oracle is not the frozen repo oracle" >&2; exit 2; }
[[ -f "$lock" && -f "$recovery_packet" && -f "$oracle" ]] || { echo "missing lock, recovery packet, or oracle" >&2; exit 2; }
[[ -z "$(git -C "$repo_root" status --short)" ]] || { echo "main repository is dirty" >&2; exit 2; }
[[ "$(jq -r .schema "$lock")" == laguna-scheduler-alignment-execution-lock-v1 ]] || { echo "scheduler lock schema mismatch" >&2; exit 2; }
[[ "$(jq -r .status "$lock")" == PASS ]] || { echo "scheduler lock is not PASS" >&2; exit 2; }
required_lock_files=$'data/laguna-device-recovery-scheduler-gate-20260802.json\ndata/laguna-scheduler-alignment-repeat-oracle-20260802.json\nexperiments/laguna-s-2.1-xpu-b70/long-context-suite-v1.json\nexperiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_scheduler_alignment.py\nexperiments/laguna-s-2.1-xpu-b70/tools/bench_laguna_long_context.py\nexperiments/laguna-s-2.1-xpu-b70/tools/build_laguna_long_context_repeat_oracle.py\nexperiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh\nexperiments/laguna-s-2.1-xpu-b70/tools/run_laguna_long_context_baseline.sh\nexperiments/laguna-s-2.1-xpu-b70/tools/run_laguna_scheduler_alignment_pair.sh\nexperiments/laguna-s-2.1-xpu-b70/tools/runtime-lock-shared-elementwise-m12.json\nexperiments/laguna-s-2.1-xpu-b70/tools/serve_laguna_long_context_nvme.sh\nrepro/laguna-s-2.1-int4-b70-102tps-20260726/verify-runtime.py'
observed_lock_files="$(jq -r '.files | if type == "object" then keys[] else error("files is not an object") end' "$lock")"
[[ "$observed_lock_files" == "$required_lock_files" ]] || { echo "scheduler lock file set mismatch" >&2; exit 2; }
while IFS=$'\t' read -r relative expected_sha; do
  actual_sha="$(sha256sum "$repo_root/$relative" | cut -d' ' -f1)"
  [[ "$actual_sha" == "$expected_sha" ]] || { echo "lock hash mismatch: $relative" >&2; exit 2; }
done < <(jq -r '.files | to_entries[] | [.key, .value] | @tsv' "$lock")

[[ "$(jq -r .status "$recovery_packet")" == PASS ]] || { echo "recovery packet is not PASS" >&2; exit 2; }
expected_boot_id="$(jq -r .boot.after_id "$recovery_packet")"
[[ "$(</proc/sys/kernel/random/boot_id)" == "$expected_boot_id" ]] || { echo "current boot differs from passed recovery boot" >&2; exit 2; }
recovery_root="$(jq -r .artifact_root "$recovery_packet")"
[[ -d "$recovery_root" && -f "$recovery_root/manifest.sha256" ]] || { echo "sealed recovery root is missing" >&2; exit 2; }
[[ -z "$(find "$recovery_root" -perm /222 -print -quit)" ]] || { echo "recovery root is not sealed read-only" >&2; exit 2; }
(cd "$recovery_root" && sha256sum -c manifest.sha256 >/dev/null) || { echo "recovery manifest verification failed" >&2; exit 2; }
[[ "$(jq -r .source_commits.vllm "$lock")" == 4ddb915284d4442885f72bed48311fd04640977c ]] || { echo "scheduler lock vLLM commit mismatch" >&2; exit 2; }
[[ "$(jq -r .source_commits.kernel "$lock")" == 99886d783372e621941228250091dc8ebdc1595d ]] || { echo "scheduler lock kernel commit mismatch" >&2; exit 2; }
[[ "$(jq -r .oracle_sha256 "$lock")" == "$(sha256sum "$oracle" | cut -d' ' -f1)" ]] || { echo "scheduler lock oracle mismatch" >&2; exit 2; }
[[ "$(jq -r .recovery_packet_sha256 "$lock")" == "$(sha256sum "$recovery_packet" | cut -d' ' -f1)" ]] || { echo "scheduler lock recovery packet mismatch" >&2; exit 2; }
! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker|torchrun' >/dev/null 2>&1 || { echo "foreign model process blocks pair" >&2; exit 2; }
! ss -H -ltn 'sport = :8000 or sport = :18080' | grep -q . || { echo "protected port is busy" >&2; exit 2; }

runs=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs
pair_root="$runs/laguna-scheduler-alignment-$tag-pair"
control_run="$runs/laguna-scheduler-alignment-$tag-A"
candidate_run="$runs/laguna-scheduler-alignment-$tag-B"
for path in "$pair_root" "$control_run" "$candidate_run"; do
  [[ ! -e "$path" && ! -L "$path" ]] || { echo "path already exists: $path" >&2; exit 2; }
done
mkdir -m 700 "$pair_root"
pair_root_created=true
finalize_pair() {
  local status="$?"
  trap - EXIT INT TERM
  if [[ "$pair_root_created" == true ]]; then
    printf 'exit_status=%s\ncompleted_at_utc=%s\n' "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      > "$pair_root/wrapper-status.txt"
    chmod -R a-w "$pair_root" 2>/dev/null || true
  fi
  exit "$status"
}
trap finalize_pair EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ "$(uname -r)" == "$(jq -r .boot.kernel "$recovery_packet")" ]] || { echo "current kernel differs from recovery packet" >&2; exit 2; }
[[ "$(cat /proc/sys/kernel/tainted)" == 0 ]] || { echo "current kernel is tainted" >&2; exit 2; }
device_specs=(
  '0000:23:00.0|card3|controlD67|renderD130'
  '0000:27:00.0|card4|controlD68|renderD131'
  '0000:43:00.0|card0|controlD64|renderD128'
  '0000:47:00.0|card2|controlD66|renderD129'
)
drm_paths=()
: > "$pair_root/current-device-identities.txt"
for spec in "${device_specs[@]}"; do
  IFS='|' read -r bdf card control render <<< "$spec"
  device_dir="/sys/bus/pci/devices/$bdf"
  [[ -d "$device_dir" ]] || { echo "missing expected B70 BDF: $bdf" >&2; exit 2; }
  [[ "$(<"$device_dir/vendor")" == 0x8086 && "$(<"$device_dir/device")" == 0xe223 ]] || { echo "PCI identity mismatch: $bdf" >&2; exit 2; }
  [[ "$(readlink -f "$device_dir/driver")" == /sys/bus/pci/drivers/xe ]] || { echo "driver mismatch: $bdf" >&2; exit 2; }
  [[ "$(readlink -f "/sys/class/drm/$card/device")" == "$(readlink -f "$device_dir")" ]] || { echo "DRM card binding mismatch: $bdf" >&2; exit 2; }
  observed_drm="$(find "$device_dir/drm" -mindepth 1 -maxdepth 1 -printf '%f\n' | LC_ALL=C sort | paste -sd, -)"
  expected_drm="$(printf '%s\n' "$card" "$control" "$render" | LC_ALL=C sort | paste -sd, -)"
  [[ "$observed_drm" == "$expected_drm" ]] || { echo "DRM node set mismatch: $bdf" >&2; exit 2; }
  for node in "$card" "$control" "$render"; do
    [[ -c "/dev/dri/$node" ]] || { echo "missing DRM character device: $node" >&2; exit 2; }
    drm_paths+=("/dev/dri/$node")
  done
  printf '%s vendor=0x8086 device=0xe223 driver=xe drm=%s\n' "$bdf" "$observed_drm" \
    >> "$pair_root/current-device-identities.txt"
done
if fuser "${drm_paths[@]}" >/dev/null 2>&1; then
  echo "foreign DRM opener blocks pair" >&2
  exit 2
fi
recovery_completed="$(jq -r .completed_at_utc "$recovery_root/summary.json")"
journalctl -k -b --since "$recovery_completed" --no-pager \
  > "$pair_root/current-kernel-journal.log"
grep -Eai \
  'guc.*(timeout|reset|error)|exec.*queue.*timeout|wedg|gpu.*(hang|reset|fault)|xe.*(timeout|reset|error|fail|fault|hang)|drm.*(timeout|reset|error|fail|fault|hang)' \
  "$pair_root/current-kernel-journal.log" > "$pair_root/current-device-error-scan.log" || true
[[ ! -s "$pair_root/current-device-error-scan.log" ]] || { echo "device error occurred after the recovery gate" >&2; exit 2; }

vllm_tree=/home/steve/src/laguna-vllm-exact-prefill-chunks-20260802
kernel_tree=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731
vllm_commit=4ddb915284d4442885f72bed48311fd04640977c
kernel_commit=99886d783372e621941228250091dc8ebdc1595d
[[ -z "$(git -C "$vllm_tree" status --short)" && "$(git -C "$vllm_tree" rev-parse HEAD)" == "$vllm_commit" ]] || { echo "frozen vLLM tree mismatch" >&2; exit 2; }
[[ -z "$(git -C "$kernel_tree" status --short)" && "$(git -C "$kernel_tree" rev-parse HEAD)" == "$kernel_commit" ]] || { echo "frozen kernel tree mismatch" >&2; exit 2; }
observed_swap_layout="$(awk 'NR > 1 { print $1 ":" $3 }' /proc/swaps | sort)"
expected_swap_layout=$'/swap-laguna-longctx.img:16777212\n/swap.img:8388604'
[[ "$observed_swap_layout" == "$expected_swap_layout" ]] || { echo "frozen 24 GiB swap layout is not active" >&2; exit 2; }
cases=laguna-lc-01024-early,laguna-lc-08192-early,laguna-lc-08192-middle,laguna-lc-08192-late,laguna-lc-16384-middle,laguna-lc-24576-middle,laguna-lc-32640-early,laguna-lc-32640-middle,laguna-lc-32640-late
printf 'tag=%s\nrepo_head=%s\nlock_sha256=%s\nrepeat_oracle=%s\nrepeat_oracle_sha256=%s\nrecovery_boot_id=%s\ncontrol_run=%s\ncandidate_run=%s\n' "$tag" "$(git -C "$repo_root" rev-parse HEAD)" "$(sha256sum "$lock" | cut -d' ' -f1)" "$oracle" "$(sha256sum "$oracle" | cut -d' ' -f1)" "$expected_boot_id" "$control_run" "$candidate_run" > "$pair_root/identity.txt"

laguna_nvme_prepare_paths
laguna_nvme_verify_model_contents > "$pair_root/model-content-verification.log" 2>&1
printf 'PASS\n' > "$pair_root/model-content-verification.status"

common_env=(
  REPRO_VLLM_TREE="$vllm_tree"
  REPRO_KERNEL_TREE="$kernel_tree"
  REPRO_EXPECTED_VLLM_COMMIT="$vllm_commit"
  REPRO_EXPECTED_KERNEL_COMMIT="$kernel_commit"
  LAGUNA_LONG_CANDIDATE_PROFILE=q12
  LAGUNA_EXACT_PREFILL_CHUNKS=1
  LAGUNA_MAX_MODEL_LEN=32768
  LAGUNA_GPU_UTIL=0.80
  LAGUNA_MIN_MEM_AVAILABLE_KB=8388608
  LAGUNA_MIN_SWAP_FREE_KB=4194304
  LAGUNA_MIN_SWAP_TOTAL_KB=25165816
  LAGUNA_REQUIRED_SWAP_LAYOUT=laguna-longctx-24g
  LAGUNA_REQUIRE_ORACLE=1
  LAGUNA_LONG_CASE_IDS="$cases"
)

env "${common_env[@]}" LAGUNA_MAX_NUM_BATCHED_TOKENS=8192 LAGUNA_MAX_NUM_SCHEDULED_TOKENS=auto LAGUNA_LONG_ORACLE="$oracle" "$runner" candidate "$control_run" 2>&1 | tee "$pair_root/control.stdout"

"$python" "$analyzer" --control-run "$control_run" --repeat-oracle "$oracle" --control-only --out "$pair_root/control-validation.json" 2>&1 | tee "$pair_root/control-validation.stdout"

env "${common_env[@]}" LAGUNA_MAX_NUM_BATCHED_TOKENS=8202 LAGUNA_MAX_NUM_SCHEDULED_TOKENS=8192 LAGUNA_LONG_ORACLE="$control_run/bench.json" "$runner" candidate "$candidate_run" 2>&1 | tee "$pair_root/candidate.stdout"

"$python" "$analyzer" --control-run "$control_run" --candidate-run "$candidate_run" --repeat-oracle "$oracle" --out "$pair_root/summary.json" 2>&1 | tee "$pair_root/analyzer.stdout"
