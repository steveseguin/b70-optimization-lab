#!/usr/bin/env bash
set -Eeuo pipefail

# Atomic, untreated-first TP1 qualification r3 for literal-current vLLM 79bb
# and exact-current XPU kernel baaa. R1 closed at a mixed-runtime host gate; r2
# passed that gate and then false-failed a procfs quiet comparison before any
# model arm. This corrected program still contains no decision, source, DSO, or
# binary overlay. A speed-only miss is evidence for a separate packet; it never
# authorizes carrying the closed 0ecc decisions in this invocation.

umask 077

mode=${1:-all}
[[ $# -le 1 && $mode == all ]] || {
  printf 'usage: %s all\n' "$0" >&2
  printf 'record-grade qualification is atomic and cannot resume individual arms\n' >&2
  exit 2
}

script_path=$(realpath -e -- "${BASH_SOURCE[0]}")
script_dir=$(dirname -- "$script_path")
repo=$(git -C "$script_dir" rev-parse --show-toplevel)
runner=$repo/experiments/qwen38-27b-b70/scripts/run-20260823-qwen38-absolute-current-main-strict-smoke.sh
receipt=$repo/experiments/qwen38-27b-b70/data/2026-08-24-qwen38-79bb395eea-absolute-current-main-build.json
suite=$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json
baseline=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json
model_manifest=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json
model_verifier=$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py
bench_helper=$repo/scripts/bench-openai-realistic-suite.py
quality_helper=$repo/scripts/qwen38-text-quality-suite.py
prereg=$repo/experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-79bb-untreated-tp1-r3-prereg.md
hardware_gate_runner=$repo/experiments/qwen38-27b-b70/scripts/run-20260824-qwen38-postreboot-hardware-gate.sh
hardware_gate=${HARDWARE_GATE_ROOT:-/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-79bb-20260824-086de284-venvlib-r3}
result_root=${RESULT_ROOT:-/home/steve/qwen38-current-main-runs/tp1-untreated-79bb-20260824-r3}
inputs=$result_root/inputs
control_cache=$result_root/control-cache
control_fresh_out=$result_root/control-fresh-diagnostic
control_replay_a_out=$result_root/control-strict-quality-replay-a
control_replay_b_out=$result_root/control-strict-replay-b
frozen_inputs_manifest_sha256=
frozen_control_cache_manifest_sha256=
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}

expected_suite_sha256=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
expected_baseline_sha256=738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18
expected_receipt_sha256=92e8fa48ad09ee025fd16a8f29440d622715df0c300fade3023317cd756d948d
expected_prereg_sha256=1427f9baf6014308b6458997f74f4c78f9a60296d4987c183d86f212ccf7ac88
expected_runner_sha256=cec5f3d852c84255822a4a5ee14d6829cd5efa6719ff9e8c59a904090d11c2b0
expected_hardware_gate_runner_sha256=84b9f5025476f40cb3218dbe513718c6d37da1e4852d17031b403fa410e4c506
expected_vllm_head=79bb395eea64dbfef99a55f010d2854db71f8571
expected_vllm_tree=3dc459a78f843186bb8a510631f9f1d34448a243
expected_kernel_head=baaa05bb4e92901219a5a072dd63f2474896f6d1
expected_kernel_tree=e7e7d1063f232a383c98c1820cebb94c45b4906e
expected_base_digest=sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876
expected_control_image_id=sha256:9f8000f2317de47098161b4da63efb61994a51d9edd8bfe902818e8e685e075a
expected_both_image_id=sha256:786681b8aa4150d30e12af93b3038a03daba110719bf650a5c9d7c8804e0bdf3
expected_host_kernel=7.0.0-30-generic
expected_host_boot_id=086de284-0771-4269-9cb2-e064fe303e40
diagnostic_floor=30.2178
strict_floor=30.31067504052998

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

for command_name in awk chmod cmp cp df docker env find findmnt flock git grep \
  jq mv pgrep realpath rg sed sha256sum sort sudo sync timeout tr uname xargs; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done

acquire_campaign_locks() {
  local device lease_fd
  muse_lock_file=/run/lock/muse-glimmer-gpu-exclusive.lock
  host_lock_file=/tmp/b70-benchmark.lock
  exec {campaign_muse_lock_fd}<>"$muse_lock_file"
  flock -n "$campaign_muse_lock_fd" || die 'Muse GPU lock is held'
  exec {campaign_host_lock_fd}<>"$host_lock_file"
  flock -n "$campaign_host_lock_fd" || die 'host benchmark lock is held'
  gpu_lease_dir=/run/user/$(id -u)/qwen36-b70-gpu-leases
  mkdir -p -- "$gpu_lease_dir"
  campaign_gpu_lease_fds=()
  for device in 0 1 2 3; do
    exec {lease_fd}>"$gpu_lease_dir/gpu${device}.lock"
    flock -n "$lease_fd" || die "GPU $device is leased"
    campaign_gpu_lease_fds+=("$lease_fd")
  done
  campaign_gpu_lease_csv=$(IFS=,; printf '%s' "${campaign_gpu_lease_fds[*]}")
}

validate_hardware_gate() {
  for required in "$hardware_gate/summary.json" "$hardware_gate/final.status" \
    "$hardware_gate/SHA256SUMS"; do
    [[ -f $required ]] || die "missing hardware-gate evidence: $required"
  done
  (
    cd "$hardware_gate"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die 'post-reboot hardware-gate evidence changed'
  [[ $(<"$hardware_gate/final.status") == exit_status=0 ]] ||
    die 'post-reboot hardware gate did not exit cleanly'
  jq -e \
    --arg boot_id "$expected_host_boot_id" \
    --arg kernel "$expected_host_kernel" \
    --arg repo_head "$(git -C "$repo" rev-parse HEAD)" '
    .schema == "neural-download-qwen38-postreboot-hardware-gate-v2" and
    .passed == true and .gate_complete == true and .failure_stage == "complete" and
    .host.boot_id == $boot_id and .host.kernel == $kernel and
    .host.taint_pre == "0" and .host.taint_post == "0" and
    .repo_head == $repo_head and .gates.four_device_identity == true and
    .gates.per_card_compute == true and .gates.four_device_peer_read == true and
    .gates.four_rank_xccl_allreduce == true and .gates.repo_postflight == true and
    .gates.atomic_lock_handoff == true and
    .gates.torch_runtime_coherent == true and
    .gates.selector_and_mask_combined == false and
    .gates.kernel_reject_events == 0
  ' "$hardware_gate/summary.json" >/dev/null ||
    die 'post-reboot hardware gate is not valid for this commit and boot'
}

for required in "$runner" "$receipt" "$suite" "$baseline" \
  "$model_manifest" "$model_verifier" "$bench_helper" "$quality_helper" \
  "$prereg" "$hardware_gate_runner"; do
  [[ -e $required ]] || die "missing input: $required"
done
[[ -r $sudo_pass_file ]] || die 'sudo password file is unreadable'
[[ $(sha256sum "$suite" | awk '{print $1}') == "$expected_suite_sha256" ]] ||
  die 'validation suite hash changed'
[[ $(sha256sum "$baseline" | awk '{print $1}') == "$expected_baseline_sha256" ]] ||
  die 'quality baseline hash changed'
[[ $(sha256sum "$receipt" | awk '{print $1}') == "$expected_receipt_sha256" ]] ||
  die 'exact 79bb build receipt changed'
[[ $(sha256sum "$prereg" | awk '{print $1}') == "$expected_prereg_sha256" ]] ||
  die '79bb untreated preregistration hash changed'
[[ $(sha256sum "$runner" | awk '{print $1}') == "$expected_runner_sha256" ]] ||
  die 'successful benchmark runner changed'
[[ $(sha256sum "$hardware_gate_runner" | awk '{print $1}') == \
   "$expected_hardware_gate_runner_sha256" ]] ||
  die 'corrected hardware-gate runner changed'
jq -e \
  --arg vllm "$expected_vllm_head" --arg vllm_tree "$expected_vllm_tree" \
  --arg kernel "$expected_kernel_head" --arg kernel_tree "$expected_kernel_tree" \
  --arg base "$expected_base_digest" --arg control "$expected_control_image_id" \
  --arg both "$expected_both_image_id" '
  .schema == "neural-download-absolute-current-main-build-v1" and
  .state == "static-preflight-passed-for-built-images-gpu-qualification-pending" and
  .mode == "--build-all" and .overlay == "none" and
  .vllm.head == $vllm and .vllm.tree == $vllm_tree and
  .kernel.head == $kernel and .kernel.tree == $kernel_tree and
  .base_digest == $base and
  .images.current_vllm_stock_kernel.built == true and
  .images.current_vllm_stock_kernel.image_id == $control and
  .images.current_vllm_stock_kernel.static_preflight_passed == true and
  .images.both_current_zero_overlay.built == true and
  .images.both_current_zero_overlay.image_id == $both and
  .images.both_current_zero_overlay.static_preflight_passed == true and
  .promotion.qualified == false
' "$receipt" >/dev/null || die 'exact 79bb build receipt contract changed'
archive_dir=$(jq -r .external_archive "$receipt")
[[ -d $archive_dir ]] || die '79bb external build archive is absent'
(
  cd "$archive_dir"
  sha256sum -c SHA256SUMS >/dev/null
) || die '79bb external build archive checksum failure'
cmp -s "$receipt" "$archive_dir/build-receipt.json" ||
  die 'tracked and archived 79bb receipts differ'
[[ $(uname -r) == "$expected_host_kernel" ]] ||
  die "host kernel changed: $(uname -r)"
[[ $(</proc/sys/kernel/random/boot_id) == "$expected_host_boot_id" ]] ||
  die 'host boot changed after preregistration'
if runtime_variable_names=$(env | sed 's/=.*//' | LC_ALL=C sort -u); then
  :
else
  die 'environment-name collection failed'
fi
if inherited_runtime_output=$(printf '%s\n' "$runtime_variable_names" |
    rg '^(ONEAPI_.*|ZE_.*|ZES_.*|SYCL_.*|UR_.*|XPU_.*|PYTHONPATH|PYTHONHOME|LD_PRELOAD|LD_LIBRARY_PATH|CCL_.*|ONECCL_.*|FI_.*|I_MPI_.*|MPI_.*|PMI_.*|PMIX_.*|TORCH_XCCL_.*|VLLM_.*)$'); then
  printf 'forbidden inherited runtime variables:\n%s\n' \
    "$inherited_runtime_output" >&2
  die 'qualification must start from an accelerator-runtime-clean environment'
else
  inherited_runtime_scan_rc=$?
fi
[[ $inherited_runtime_scan_rc -eq 1 ]] ||
  die 'inherited runtime environment scan failed'
timeout --signal=TERM --kill-after=5s 20s sudo -S -p '' -v \
  <"$sudo_pass_file" || die 'sudo authentication preflight failed'
lab_status=$(git -C "$repo" status --porcelain=v1 --untracked-files=all) ||
  die 'lab repository status check failed'
[[ -z $lab_status ]] ||
  die 'lab repository must be clean before the atomic health/qualification chain'
[[ $(git -C "$repo" branch --show-current) == main ]] ||
  die 'lab repository must be on main'
lab_head=$(git -C "$repo" rev-parse HEAD)
[[ $(git -C "$repo" rev-parse origin/main) == "$lab_head" ]] ||
  die 'local main must equal origin/main'
[[ $(timeout --signal=TERM --kill-after=5s 30s \
    git -C "$repo" ls-remote --exit-code origin refs/heads/main |
    awk 'NR == 1 {print $1}') == "$lab_head" ]] ||
  die 'local main must equal live origin/main'
[[ $(timeout --signal=TERM --kill-after=5s 30s \
    git ls-remote --exit-code https://github.com/vllm-project/vllm.git \
    refs/heads/main | awk 'NR == 1 {print $1}') == "$expected_vllm_head" ]] ||
  die 'vLLM main advanced before the hardware gate; rebuild first'
[[ $(timeout --signal=TERM --kill-after=5s 30s git ls-remote --exit-code \
    https://github.com/vllm-project/vllm-xpu-kernels.git refs/heads/main |
    awk 'NR == 1 {print $1}') == "$expected_kernel_head" ]] ||
  die 'XPU-kernel main advanced before the hardware gate; rebuild first'
live_base_digest=$(timeout --signal=TERM --kill-after=5s 60s \
  sudo -S -p '' docker buildx imagetools inspect \
  vllm/vllm-openai-xpu:nightly --format '{{.Manifest.Digest}}' \
  <"$sudo_pass_file")
[[ $live_base_digest == "$expected_base_digest" ]] ||
  die 'official nightly base advanced before the hardware gate; rebuild first'
[[ $result_root == /* && $hardware_gate == /* ]] ||
  die 'campaign and hardware-gate roots must be absolute'
canonical_result_root=$(realpath -m -- "$result_root")
canonical_hardware_gate=$(realpath -m -- "$hardware_gate")
if [[ $canonical_result_root == "$canonical_hardware_gate" ||
      $canonical_result_root == "$canonical_hardware_gate/"* ||
      $canonical_hardware_gate == "$canonical_result_root/"* ]]; then
  die 'campaign and hardware-gate roots must be disjoint and non-nested'
fi
[[ ! -e $result_root ]] || die "result root already exists: $result_root"
[[ ! -e $hardware_gate ]] ||
  die "fresh atomic hardware-gate root already exists: $hardware_gate"
result_parent=$(dirname -- "$result_root")
hardware_parent=$(dirname -- "$hardware_gate")
[[ -d $result_parent && -d $hardware_parent ]] ||
  die 'campaign and hardware-gate parents must already exist'
[[ $(findmnt -n -o FSTYPE --target "$result_parent") == ext4 &&
   $(findmnt -n -o FSTYPE --target "$hardware_parent") == ext4 ]] ||
  die 'campaign and hardware-gate evidence must be on ext4'
available_kib=$(df -Pk "$result_parent" | awk 'NR == 2 {print $4}')
[[ $available_kib =~ ^[0-9]+$ ]] || die 'could not read qualification free space'
(( available_kib >= 12 * 1024 * 1024 )) ||
  die 'qualification requires at least 12 GiB free'
[[ $(sudo -S -p '' docker image inspect "$expected_control_image_id" \
    --format '{{.Id}}' <"$sudo_pass_file") == "$expected_control_image_id" ]] ||
  die 'exact 79bb stock-kernel image is absent'
[[ $(sudo -S -p '' docker image inspect "$expected_both_image_id" \
    --format '{{.Id}}' <"$sudo_pass_file") == "$expected_both_image_id" ]] ||
  die 'exact 79bb both-current image is absent'

acquire_campaign_locks
RESULT_ROOT="$hardware_gate" SUDO_PASS_FILE="$sudo_pass_file" \
QWEN_CURRENT_MUSE_LOCK_FD="$campaign_muse_lock_fd" \
QWEN_CURRENT_HOST_LOCK_FD="$campaign_host_lock_fd" \
QWEN_CURRENT_GPU_LEASE_FDS="$campaign_gpu_lease_csv" \
  "$hardware_gate_runner"
validate_hardware_gate

prepare_inputs() {
  [[ ! -e $result_root ]] || die "result root already exists: $result_root"
  mkdir -p -- "$inputs"
  cp --reflink=never -- "$runner" "$inputs/strict-smoke.sh"
  cp --reflink=never -- "$script_path" "$inputs/qualification-runner.sh"
  cp --reflink=never -- "$receipt" "$inputs/build-receipt.json"
  cp --reflink=never -- "$suite" "$inputs/validation-suite.json"
  cp --reflink=never -- "$baseline" "$inputs/quality-baseline.json"
  cp --reflink=never -- "$model_manifest" "$inputs/model-manifest.json"
  cp --reflink=never -- "$model_verifier" "$inputs/verify-model-direct.py"
  cp --reflink=never -- "$bench_helper" "$inputs/bench-openai-realistic-suite.py"
  cp --reflink=never -- "$quality_helper" "$inputs/qwen38-text-quality-suite.py"
  cp --reflink=never -- "$prereg" "$inputs/preregistration.md"
  cp --reflink=never -- "$hardware_gate/summary.json" \
    "$inputs/postreboot-hardware-gate-summary.json"
  cp --reflink=never -- "$hardware_gate/final.status" \
    "$inputs/postreboot-hardware-gate-final.status"
  cp --reflink=never -- "$hardware_gate/SHA256SUMS" \
    "$inputs/postreboot-hardware-gate-SHA256SUMS"
  git -C "$repo" rev-parse HEAD >"$inputs/lab-head.txt"
  uname -r >"$inputs/host-kernel-release.txt"
  uname -a >"$inputs/host-uname.txt"
  cp --reflink=never -- /proc/sys/kernel/random/boot_id "$inputs/host-boot-id.txt"
  cp --reflink=never -- /proc/cmdline "$inputs/host-cmdline.txt"
  (
    cd "$inputs"
    find . -type f ! -name SHA256SUMS -print0 | sort -z |
      xargs -0 sha256sum >SHA256SUMS
  )
  frozen_inputs_manifest_sha256=$(sha256sum "$inputs/SHA256SUMS" |
    awk '{print $1}')
  [[ $frozen_inputs_manifest_sha256 =~ ^[0-9a-f]{64}$ ]] ||
    die 'could not freeze the input-manifest digest'
  find "$inputs" -type f -exec chmod 0444 {} +
  chmod 0555 "$inputs/strict-smoke.sh" "$inputs/qualification-runner.sh" \
    "$inputs/verify-model-direct.py"
  find "$inputs" -type d -exec chmod 0555 {} +
  verify_inputs
}

verify_inputs() {
  local executable_inputs writable_input writable_input_dir
  [[ -d $inputs ]] || die 'frozen input directory is absent'
  [[ $frozen_inputs_manifest_sha256 =~ ^[0-9a-f]{64}$ ]] ||
    die 'original frozen input-manifest digest is absent'
  [[ $(sha256sum "$inputs/SHA256SUMS" | awk '{print $1}') == \
     "$frozen_inputs_manifest_sha256" ]] ||
    die 'frozen input manifest itself changed'
  (
    cd "$inputs"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die 'frozen input snapshot changed'
  [[ $(sha256sum "$inputs/build-receipt.json" | awk '{print $1}') == \
     "$expected_receipt_sha256" ]] ||
    die 'frozen build receipt is not the preregistered receipt'
  [[ $(sha256sum "$inputs/validation-suite.json" | awk '{print $1}') == \
     "$expected_suite_sha256" ]] ||
    die 'frozen validation suite is not the preregistered suite'
  [[ $(sha256sum "$inputs/quality-baseline.json" | awk '{print $1}') == \
     "$expected_baseline_sha256" ]] ||
    die 'frozen quality baseline is not the preregistered baseline'
  [[ $(sha256sum "$inputs/preregistration.md" | awk '{print $1}') == \
     "$expected_prereg_sha256" ]] ||
    die 'frozen preregistration is not exact'
  writable_input=$(find "$inputs" -type f -perm /222 -print -quit) ||
    die 'frozen input permission scan failed'
  [[ -z $writable_input ]] || die "frozen input remains writable: $writable_input"
  writable_input_dir=$(find "$inputs" -type d -perm /222 -print -quit) ||
    die 'frozen input-directory permission scan failed'
  [[ -z $writable_input_dir ]] ||
    die "frozen input directory remains writable: $writable_input_dir"
  executable_inputs=$(
    cd "$inputs"
    find . -type f -perm /111 -printf '%P\n' | LC_ALL=C sort
  ) || die 'frozen input executable scan failed'
  [[ $executable_inputs == \
     $'qualification-runner.sh\nstrict-smoke.sh\nverify-model-direct.py' ]] ||
    die 'frozen input executable set changed'
  cmp -s "$script_path" "$inputs/qualification-runner.sh" ||
    die 'live wrapper differs from frozen wrapper'
  [[ $(<"$inputs/host-kernel-release.txt") == "$expected_host_kernel" ]] ||
    die 'frozen host kernel is not the preregistered kernel'
  [[ $(uname -r) == "$(<"$inputs/host-kernel-release.txt")" ]] ||
    die 'host kernel changed between untreated arms'
  uname -a | cmp -s - "$inputs/host-uname.txt" ||
    die 'host uname changed between untreated arms'
  cmp -- /proc/sys/kernel/random/boot_id \
    "$inputs/host-boot-id.txt" >/dev/null ||
    die 'host rebooted between untreated arms'
  [[ $(<"$inputs/host-boot-id.txt") == "$expected_host_boot_id" ]] ||
    die 'frozen host boot is not the preregistered boot'
  cmp -- /proc/cmdline "$inputs/host-cmdline.txt" >/dev/null ||
    die 'host command line changed between untreated arms'
  cmp -s "$hardware_gate/SHA256SUMS" \
    "$inputs/postreboot-hardware-gate-SHA256SUMS" ||
    die 'post-reboot hardware-gate manifest changed between untreated arms'
  (
    cd "$hardware_gate"
    sha256sum -c "$inputs/postreboot-hardware-gate-SHA256SUMS" >/dev/null
  ) || die 'post-reboot hardware-gate evidence changed between untreated arms'
  cmp -s "$hardware_gate/summary.json" \
    "$inputs/postreboot-hardware-gate-summary.json" ||
    die 'post-reboot hardware-gate summary changed between untreated arms'
  cmp -s "$hardware_gate/final.status" \
    "$inputs/postreboot-hardware-gate-final.status" ||
    die 'post-reboot hardware-gate status changed between untreated arms'
  live_lab_status=$(git -C "$repo" status --porcelain=v1 --untracked-files=all) ||
    die 'lab repository status check failed between untreated arms'
  [[ -z $live_lab_status ]] ||
    die 'lab repository became dirty between untreated arms'
  [[ $(git -C "$repo" branch --show-current) == main ]] ||
    die 'lab repository left main between untreated arms'
  frozen_lab_head=$(<"$inputs/lab-head.txt")
  [[ $(git -C "$repo" rev-parse HEAD) == "$frozen_lab_head" ]] ||
    die 'lab commit changed between untreated arms'
  [[ $(git -C "$repo" rev-parse origin/main) == "$frozen_lab_head" ]] ||
    die 'local origin/main changed between untreated arms'
  live_lab_head=$(timeout --signal=TERM --kill-after=5s 30s \
    git -C "$repo" ls-remote --exit-code origin refs/heads/main |
    awk 'NR == 1 {print $1}')
  [[ $live_lab_head == "$frozen_lab_head" ]] ||
    die 'live lab origin/main changed between untreated arms'
  live_vllm_head=$(timeout --signal=TERM --kill-after=5s 30s git ls-remote --exit-code \
    https://github.com/vllm-project/vllm.git refs/heads/main |
    awk 'NR == 1 {print $1}')
  [[ $live_vllm_head == "$expected_vllm_head" ]] ||
    die 'vLLM main advanced during untreated qualification'
  live_kernel_head=$(timeout --signal=TERM --kill-after=5s 30s git ls-remote --exit-code \
    https://github.com/vllm-project/vllm-xpu-kernels.git refs/heads/main |
    awk 'NR == 1 {print $1}')
  [[ $live_kernel_head == "$expected_kernel_head" ]] ||
    die 'XPU-kernel main advanced during untreated qualification'
  live_base_digest=$(timeout --signal=TERM --kill-after=5s 60s \
    sudo -S -p '' docker buildx imagetools inspect \
    vllm/vllm-openai-xpu:nightly --format '{{.Manifest.Digest}}' \
    <"$sudo_pass_file")
  [[ $live_base_digest == "$expected_base_digest" ]] ||
    die 'official nightly base advanced during untreated qualification'
  [[ $(sudo -S -p '' docker image inspect "$expected_both_image_id" \
      --format '{{.Id}}' <"$sudo_pass_file") == "$expected_both_image_id" ]] ||
    die 'exact current image is absent or changed'
}

read_median_or_null() {
  local bench_json=$1
  if [[ -f $bench_json ]]; then
    jq -cer '.summary.tok_s_1_100_intervals_after_ttft.median // empty' \
      "$bench_json" 2>/dev/null || printf 'null\n'
  else
    printf 'null\n'
  fi
}

read_status_or_missing() {
  local status_file=$1
  if [[ -f $status_file ]]; then
    tr '\n' ' ' <"$status_file" | sed 's/[[:space:]]*$//'
  else
    printf 'missing'
  fi
}

write_root_status() {
  local state=$1
  local status_tmp="$result_root/.final.status.tmp.$$"
  printf '%s\n' "$state" >"$status_tmp" || return 1
  mv -f -- "$status_tmp" "$result_root/final.status" || return 1
}

write_campaign_evidence() {
  local manifest_tmp="$result_root/.campaign-evidence.sha256.tmp.$$"
  local digest_tmp="$result_root/.campaign-evidence.sha256.digest.tmp.$$"
  local symlink_output

  symlink_output=$(
    cd "$result_root"
    find . -path './control-cache' -prune -o -type l -print
  ) || return 1
  [[ -z $symlink_output ]] || {
    printf 'refusing to seal symlinked campaign evidence:\n%s\n' \
      "$symlink_output" >&2
    return 1
  }

  (
    cd "$result_root"
    find . -path './control-cache' -prune -o -type f \
      ! -name 'campaign-evidence.sha256' \
      ! -name 'campaign-evidence.sha256.digest' \
      ! -name '*.tmp' ! -name '*.tmp.*' ! -name '.tmp.*' -print0 |
      LC_ALL=C sort -z | xargs -0 -r sha256sum
  ) >"$manifest_tmp" || return 1
  mv -f -- "$manifest_tmp" "$result_root/campaign-evidence.sha256" || return 1
  sha256sum "$result_root/campaign-evidence.sha256" | awk '{print $1}' \
    >"$digest_tmp" || return 1
  mv -f -- "$digest_tmp" "$result_root/campaign-evidence.sha256.digest" ||
    return 1
  (
    cd "$result_root"
    sha256sum -c campaign-evidence.sha256 >/dev/null
  ) || return 1
  [[ $(sha256sum "$result_root/campaign-evidence.sha256" | awk '{print $1}') == \
     "$(<"$result_root/campaign-evidence.sha256.digest")" ]]
}

seal_campaign_status() {
  local state=$1
  write_root_status "$state"
  write_campaign_evidence
  sync -f "$result_root"
}

root_exit() {
  local rc=$? failure_rc failure_tmp root_state
  trap - EXIT
  trap '' INT TERM HUP
  if [[ $rc -ne 0 && -d $result_root ]]; then
    set +e
    failure_rc=$rc
    root_state="failed-incomplete mode=$mode rc=$rc"
    if ! write_root_status "$root_state"; then
      failure_rc=95
    fi
    failure_tmp="$result_root/.campaign-failure.json.tmp.$$"
    if ! jq -n \
      --arg state "$root_state" --arg mode "$mode" --argjson rc "$rc" \
      --arg host_kernel "$(uname -r)" \
      --arg boot_id "$(</proc/sys/kernel/random/boot_id)" \
      --arg control_fresh_status "$(read_status_or_missing "$control_fresh_out/final.status")" \
      --arg control_replay_a_status "$(read_status_or_missing "$control_replay_a_out/final.status")" \
      --arg control_replay_b_status "$(read_status_or_missing "$control_replay_b_out/final.status")" \
      --argjson control_diagnostic_median "$(read_median_or_null "$control_fresh_out/bench.json")" \
      --argjson control_strict_a_median "$(read_median_or_null "$control_replay_a_out/bench.json")" \
      --argjson control_strict_b_median "$(read_median_or_null "$control_replay_b_out/bench.json")" \
      --arg vllm_head "$expected_vllm_head" \
      --arg kernel_head "$expected_kernel_head" \
      --arg base_digest "$expected_base_digest" \
      --arg image_id "$expected_both_image_id" \
      --arg receipt_sha256 "$expected_receipt_sha256" '{
        schema: "neural-download-current-main-tp1-untreated-failure-v1",
        state: $state,
        mode: $mode,
        exit_code: $rc,
        host: {kernel: $host_kernel, boot_id: $boot_id},
        identity: {
          vllm_head: $vllm_head,
          kernel_head: $kernel_head,
          base_digest: $base_digest,
          image_id: $image_id,
          receipt_sha256: $receipt_sha256
        },
        arms: {
          control_fresh: {status: $control_fresh_status, median_tok_s: $control_diagnostic_median},
          control_replay_a: {status: $control_replay_a_status, median_tok_s: $control_strict_a_median},
          control_replay_b: {status: $control_replay_b_status, median_tok_s: $control_strict_b_median}
        }
      }' >"$failure_tmp" ||
        ! mv -f -- "$failure_tmp" "$result_root/campaign-failure.json"; then
      failure_rc=96
      root_state="failed-incomplete mode=$mode rc=$rc failure-json=failed"
      write_root_status "$root_state" || true
    fi
    if ! write_campaign_evidence; then
      failure_rc=97
      root_state="failed-incomplete mode=$mode rc=$rc evidence-seal=failed"
      write_root_status "$root_state" || true
    elif ! sync -f "$result_root"; then
      failure_rc=98
      root_state="failed-incomplete mode=$mode rc=$rc sync=failed"
      write_root_status "$root_state" || true
      write_campaign_evidence || true
      sync -f "$result_root" || true
    fi
    rc=$failure_rc
  fi
  exit "$rc"
}
trap root_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

run_clean_env() {
  env -u PYTHONHASHSEED \
    -u VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE \
    -u VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING \
    -u TRITON_CACHE_AUTOTUNING -u VLLM_XPU_ENABLE_XPU_GRAPH \
    -u EXTRA_VLLM_ARGS -u PROMPT_IDS -u ONEAPI_DEVICE_SELECTOR \
    -u ZE_AFFINITY_MASK -u SYCL_DEVICE_FILTER -u SYCL_DEVICE_ALLOWLIST \
    -u UR_DEVICE_SELECTORS -u XPU_GRAPH -u COMPILATION_CONFIG \
    -u PYTHONPATH -u PYTHONHOME -u LD_PRELOAD -u LD_LIBRARY_PATH \
    -u QUALITY_BASELINE_JSON -u QUALITY_REQUIRE_BASELINE \
    -u CACHE_POLICY -u EXPECTED_CACHE_MANIFEST_SHA256 \
    -u BEST_CONFIG_SEED_DIR -u EXPECTED_BEST_CONFIG_SEED_COUNT \
    -u EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256 \
    -u BEST_CONFIG_TARGET_AOT_NAMESPACE \
    -u EXPECTED_CACHE_OUTER_NAMESPACE -u EXPECTED_CACHE_CODE_HASH \
    -u EXPECTED_CACHE_COMPILER_HASH -u EXPECTED_CACHE_CONFIG_HASH \
    -u EXPECTED_CACHE_ENV_SHA256 -u EXPECTED_COMPUTATION_GRAPH_SHA256S \
    "$@"
}

common_env=(
  LAB_REPO_ROOT="$repo"
  CURRENT_MAIN_BUILD_RECEIPT="$inputs/build-receipt.json"
  CURRENT_MAIN_MODEL_MANIFEST="$inputs/model-manifest.json"
  CURRENT_MAIN_MODEL_VERIFIER="$inputs/verify-model-direct.py"
  CURRENT_MAIN_BENCH_HELPER="$inputs/bench-openai-realistic-suite.py"
  CURRENT_MAIN_QUALITY_HELPER="$inputs/qwen38-text-quality-suite.py"
  SUDO_PASS_FILE="$sudo_pass_file"
  VLLM_XPU_GRAPH=1
  PYTHONHASHSEED_MODE=zero
  PYTHONHASHSEED=0
  MAX_TOKENS=512
  BENCH=1
  CANARY=1
  RETURN_TOKEN_IDS=1
  QWEN_CURRENT_MUSE_LOCK_FD="$campaign_muse_lock_fd"
  QWEN_CURRENT_HOST_LOCK_FD="$campaign_host_lock_fd"
  QWEN_CURRENT_GPU_LEASE_FD="${campaign_gpu_lease_fds[0]}"
)

write_speed_gate() {
  local destination=$1 actual=$2 floor=$3
  if awk -v actual="$actual" -v floor="$floor" \
      'BEGIN {exit !(actual >= floor)}'; then
    printf 'pass actual=%s floor=%s\n' "$actual" "$floor" >"$destination"
  else
    printf 'fail actual=%s floor=%s\n' "$actual" "$floor" >"$destination"
  fi
}

stop_after_non_speed_failure() {
  local arm_name=$1 arm_out=$2 arm_rc=$3 arm_status failure_tmp
  verify_inputs
  [[ $arm_rc -eq 1 && -f $arm_out/qualification-failure.class &&
     -f $arm_out/qualification-failure.reason.txt &&
     -f $arm_out/final.status ]] ||
    die "invalid non-speed failure evidence for $arm_name"
  [[ $(<"$arm_out/qualification-failure.class") == \
     non-speed-qualification-gate ]] ||
    die "non-speed failure class is invalid for $arm_name"
  arm_status=$(<"$arm_out/final.status")
  case $arm_status in
    'fail rc=1'|'fail-prelaunch rc=1') ;;
    *) die "non-speed failure cleanup did not seal cleanly for $arm_name" ;;
  esac

  trap '' INT TERM HUP
  failure_tmp="$result_root/.control-non-speed-failure.json.tmp.$$"
  jq -n \
    --arg arm "$arm_name" --argjson arm_exit_code "$arm_rc" \
    --arg reason "$(<"$arm_out/qualification-failure.reason.txt")" \
    --arg arm_status "$arm_status" \
    --arg vllm_head "$expected_vllm_head" \
    --arg kernel_head "$expected_kernel_head" \
    --arg base_digest "$expected_base_digest" \
    --arg image_id "$expected_both_image_id" \
    --arg boot_id "$expected_host_boot_id" '{
      schema: "neural-download-current-main-tp1-untreated-non-speed-failure-v1",
      state: "control-non-speed-failure",
      arm: $arm,
      arm_exit_code: $arm_exit_code,
      reason: $reason,
      arm_status: $arm_status,
      identity: {
        vllm_head: $vllm_head,
        kernel_head: $kernel_head,
        base_digest: $base_digest,
        image_id: $image_id,
        boot_id: $boot_id
      }
    }' >"$failure_tmp"
  mv -f -- "$failure_tmp" "$result_root/control-non-speed-failure.json"
  seal_campaign_status 'control-non-speed-failure'
  trap - EXIT
  exit 11
}

run_strict_arm() {
  local arm_name=$1 arm_out=$2 arm_rc
  shift 2
  set +e
  "$@"
  arm_rc=$?
  set -e
  [[ $arm_rc -ne 0 ]] || return 0
  if [[ $arm_rc -eq 1 && -f $arm_out/qualification-failure.class ]]; then
    stop_after_non_speed_failure "$arm_name" "$arm_out" "$arm_rc"
  fi
  return "$arm_rc"
}

run_control_fresh() {
  prepare_inputs
  verify_inputs
  run_strict_arm control-fresh "$control_fresh_out" \
    run_clean_env "${common_env[@]}" \
    CACHE_POLICY=fresh NATURAL_EOS=0 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19761 \
      "$control_fresh_out" "$inputs/validation-suite.json" "$control_cache"
  frozen_control_cache_manifest_sha256=$(
    <"$control_fresh_out/cache-manifest.post.sha256.digest"
  )
  [[ $frozen_control_cache_manifest_sha256 =~ ^[0-9a-f]{64}$ ]] ||
    die 'fresh arm did not produce a valid cache-manifest digest'
  [[ $(sha256sum "$control_fresh_out/cache-manifest.post.sha256" |
      awk '{print $1}') == "$frozen_control_cache_manifest_sha256" ]] ||
    die 'fresh cache manifest does not match its frozen digest'
  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$control_fresh_out/bench.json")
  write_speed_gate "$control_fresh_out/current-base-speed-gate.status" \
    "$actual" "$diagnostic_floor"
  verify_inputs
  write_root_status 'control-fresh-complete-awaiting-replay-a'
}

require_control_fresh() {
  verify_inputs
  [[ $frozen_control_cache_manifest_sha256 =~ ^[0-9a-f]{64}$ ]] ||
    die 'original fresh cache-manifest digest is absent'
  [[ $(<"$control_fresh_out/cache-manifest.post.sha256.digest") == \
     "$frozen_control_cache_manifest_sha256" ]] ||
    die 'fresh cache-manifest digest changed between arms'
  [[ $(sha256sum "$control_fresh_out/cache-manifest.post.sha256" |
      awk '{print $1}') == "$frozen_control_cache_manifest_sha256" ]] ||
    die 'fresh cache manifest changed between arms'
  [[ $(<"$control_fresh_out/final.status") == pass ]] ||
    die 'untreated control fresh arm did not pass its non-speed gates'
  grep -Eq '^(pass|fail) ' "$control_fresh_out/current-base-speed-gate.status" ||
    die 'untreated control fresh speed gate is absent'
}

run_control_replay_a() {
  require_control_fresh
  run_strict_arm control-replay-a "$control_replay_a_out" \
    run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay \
    EXPECTED_CACHE_MANIFEST_SHA256="$frozen_control_cache_manifest_sha256" \
    NATURAL_EOS=1 QUALITY=1 QUALITY_REQUIRE_BASELINE=1 \
    QUALITY_BASELINE_JSON="$inputs/quality-baseline.json" \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19762 \
      "$control_replay_a_out" "$inputs/validation-suite.json" "$control_cache"
  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$control_replay_a_out/bench.json")
  write_speed_gate "$control_replay_a_out/current-base-strict-a-gate.status" \
    "$actual" "$strict_floor"
  verify_inputs
  write_root_status 'control-replay-a-complete-awaiting-replay-b'
}

require_control_replay_a() {
  require_control_fresh
  [[ $(<"$control_replay_a_out/final.status") == pass ]] ||
    die 'untreated control replay A did not pass its non-speed gates'
  grep -Eq '^(pass|fail) ' \
    "$control_replay_a_out/current-base-strict-a-gate.status" ||
    die 'untreated control replay A speed gate is absent'
  [[ $(sha256sum "$control_replay_a_out/cache-manifest.pre.sha256" |
      awk '{print $1}') == "$frozen_control_cache_manifest_sha256" &&
     $(sha256sum "$control_replay_a_out/cache-manifest.post.sha256" |
      awk '{print $1}') == "$frozen_control_cache_manifest_sha256" ]] ||
    die 'replay A cache evidence diverges from the frozen fresh manifest'
  cmp -s "$control_replay_a_out/cache-manifest.pre.sha256" \
    "$control_replay_a_out/cache-manifest.post.sha256" ||
    die 'replay A cache evidence changed after the arm'
}

run_control_replay_b() {
  require_control_replay_a
  run_strict_arm control-replay-b "$control_replay_b_out" \
    run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay \
    EXPECTED_CACHE_MANIFEST_SHA256="$frozen_control_cache_manifest_sha256" \
    NATURAL_EOS=1 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19763 \
      "$control_replay_b_out" "$inputs/validation-suite.json" "$control_cache"
  [[ $(<"$control_replay_b_out/final.status") == pass ]] ||
    die 'untreated control replay B did not pass its non-speed gates'
  actual_b=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$control_replay_b_out/bench.json")
  write_speed_gate "$control_replay_b_out/current-base-strict-b-gate.status" \
    "$actual_b" "$strict_floor"
  require_control_replay_a
  [[ $(sha256sum "$control_replay_b_out/cache-manifest.pre.sha256" |
      awk '{print $1}') == "$frozen_control_cache_manifest_sha256" &&
     $(sha256sum "$control_replay_b_out/cache-manifest.post.sha256" |
      awk '{print $1}') == "$frozen_control_cache_manifest_sha256" ]] ||
    die 'replay B cache evidence diverges from the frozen fresh manifest'
  cmp -s "$control_replay_b_out/cache-manifest.pre.sha256" \
    "$control_replay_b_out/cache-manifest.post.sha256" ||
    die 'replay B cache evidence changed after the arm'

  control_inputs_manifest_sha256=$frozen_inputs_manifest_sha256
  control_cache_manifest_sha=$frozen_control_cache_manifest_sha256
  control_replay_a_cache_immutable=true
  control_replay_b_cache_immutable=true
  control_source_identity_exact=true
  for arm_out in "$control_fresh_out" "$control_replay_a_out" \
      "$control_replay_b_out"; do
    [[ $(<"$arm_out/upstream-vllm.pre.txt") == "$expected_vllm_head" &&
       $(<"$arm_out/upstream-vllm.post.txt") == "$expected_vllm_head" &&
       $(<"$arm_out/upstream-kernel.pre.txt") == "$expected_kernel_head" &&
       $(<"$arm_out/upstream-kernel.post.txt") == "$expected_kernel_head" &&
       $(<"$arm_out/upstream-nightly-base.pre.txt") == "$expected_base_digest" &&
       $(<"$arm_out/upstream-nightly-base.post.txt") == "$expected_base_digest" ]] ||
      control_source_identity_exact=false
  done

  jq -n \
    --arg run_root "$result_root" \
    --arg vllm_head "$expected_vllm_head" --arg vllm_tree "$expected_vllm_tree" \
    --arg kernel_head "$expected_kernel_head" --arg kernel_tree "$expected_kernel_tree" \
    --arg base_digest "$expected_base_digest" --arg image_id "$expected_both_image_id" \
    --arg receipt_sha256 "$expected_receipt_sha256" \
    --arg lab_head "$(<"$inputs/lab-head.txt")" \
    --arg host_kernel "$(<"$inputs/host-kernel-release.txt")" \
    --arg host_uname "$(<"$inputs/host-uname.txt")" \
    --arg host_boot_id "$(<"$inputs/host-boot-id.txt")" \
    --arg inputs_manifest_sha256 "$control_inputs_manifest_sha256" \
    --arg cache_manifest_sha256 "$control_cache_manifest_sha" \
    --argjson replay_a_cache_immutable "$control_replay_a_cache_immutable" \
    --argjson replay_b_cache_immutable "$control_replay_b_cache_immutable" \
    --argjson source_identity_exact "$control_source_identity_exact" \
    --argjson diagnostic_floor "$diagnostic_floor" --argjson strict_floor "$strict_floor" \
    --slurpfile d "$control_fresh_out/bench.json" \
    --slurpfile a "$control_replay_a_out/bench.json" \
    --slurpfile b "$control_replay_b_out/bench.json" \
    --slurpfile md "$control_fresh_out/model-direct-and-ordinary-verify.json" \
    --slurpfile ma "$control_replay_a_out/model-direct-and-ordinary-verify.json" \
    --slurpfile mb "$control_replay_b_out/model-direct-and-ordinary-verify.json" \
    --slurpfile cd "$control_fresh_out/canary.json" \
    --slurpfile ca "$control_replay_a_out/canary.json" \
    --slurpfile cb "$control_replay_b_out/canary.json" \
    --slurpfile q "$control_replay_a_out/quality.json" '
    [range(0; ($a[0].rows | length)) as $i | {
      prompt_id: $a[0].rows[$i].prompt_id,
      prompt_id_matches: ($a[0].rows[$i].prompt_id == $b[0].rows[$i].prompt_id),
      full_token_ids_equal: ($a[0].rows[$i].token_ids == $b[0].rows[$i].token_ids),
      first_100_token_ids_equal: ($a[0].rows[$i].token_ids[:100] == $b[0].rows[$i].token_ids[:100])
    }] as $pairs |
    (($md[0].status == "verified" and ($md[0].files | length) == 19 and
      all($md[0].files[]; .ok == true) and
      $ma[0].status == "verified" and ($ma[0].files | length) == 19 and
      all($ma[0].files[]; .ok == true) and
      $mb[0].status == "verified" and ($mb[0].files | length) == 19 and
      all($mb[0].files[]; .ok == true))) as $model_ok |
    (($cd[0].content == "14" and $cd[0].cached_tokens == 0 and
      $ca[0].content == "14" and $ca[0].cached_tokens == 0 and
      $cb[0].content == "14" and $cb[0].cached_tokens == 0)) as $canary_ok |
    (($d[0].realistic_final_gate.passed == true and
      $a[0].realistic_final_gate.passed == true and
      $b[0].realistic_final_gate.passed == true and
      $d[0].fresh_response_validity.cached_tokens_all_zero == true and
      $a[0].fresh_response_validity.cached_tokens_all_zero == true and
      $b[0].fresh_response_validity.cached_tokens_all_zero == true)) as $bench_ok |
    (($q[0].pass_all == true and $q[0].baseline_match_all == true and
      ($q[0].exact_cases | length) == 7 and
      ($q[0].repeat_case.runs | length) == 8 and
      $q[0].long_context_case.requested_context_tokens == 8192 and
      $q[0].long_context_case.actual_prompt_tokens == 7617 and
      ($q[0].baseline_comparisons | length) == 24)) as $quality_ok |
    (($replay_a_cache_immutable and $replay_b_cache_immutable and
      $source_identity_exact and $model_ok and $canary_ok and $bench_ok and
      $quality_ok and all($pairs[]; .prompt_id_matches))) as $all_non_speed |
    {
      schema: "neural-download-current-main-tp1-untreated-control-result-v1",
      state: "complete",
      run_root: $run_root,
      role: "same-boot fresh untreated literal-current control",
      identity: {
        vllm_head: $vllm_head, vllm_tree: $vllm_tree,
        kernel_head: $kernel_head, kernel_tree: $kernel_tree,
        base_digest: $base_digest, image_id: $image_id,
        receipt_sha256: $receipt_sha256, lab_head: $lab_head
      },
      host: {kernel: $host_kernel, uname: $host_uname, boot_id: $host_boot_id},
      floors_tok_s: {diagnostic: $diagnostic_floor, strict: $strict_floor},
      medians_tok_s: {
        diagnostic: $d[0].summary.tok_s_1_100_intervals_after_ttft.median,
        strict_a: $a[0].summary.tok_s_1_100_intervals_after_ttft.median,
        strict_b: $b[0].summary.tok_s_1_100_intervals_after_ttft.median
      },
      speed_gates: {
        diagnostic: ($d[0].summary.tok_s_1_100_intervals_after_ttft.median >= $diagnostic_floor),
        strict_a: ($a[0].summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor),
        strict_b: ($b[0].summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor)
      },
      evidence: {
        postreboot_hardware_gate_pass: true,
        frozen_inputs_manifest_sha256: $inputs_manifest_sha256,
        compiled_cache_manifest_sha256: $cache_manifest_sha256,
        replay_a_full_cache_immutable: $replay_a_cache_immutable,
        replay_b_full_cache_immutable: $replay_b_cache_immutable,
        exact_source_identity_pre_and_post_all_arms: $source_identity_exact,
        repo_and_host_postflight_pass: true,
        model_identity_all_arms: $model_ok,
        canary_all_arms: $canary_ok,
        realistic_benchmark_all_arms: $bench_ok,
        quality_battery: $quality_ok,
        prompt_order_matches: (all($pairs[]; .prompt_id_matches)),
        all_non_speed_gates_pass: $all_non_speed
      },
      replay_token_comparison: {
        prompt_count: ($pairs | length),
        full_token_array_matches: ([$pairs[] | select(.full_token_ids_equal)] | length),
        first_100_token_array_matches: ([$pairs[] | select(.first_100_token_ids_equal)] | length)
      },
      qualification_ready: (
        $all_non_speed and
        $d[0].summary.tok_s_1_100_intervals_after_ttft.median >= $diagnostic_floor and
        $a[0].summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor and
        $b[0].summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor
      )
    }
  ' >"$result_root/.control-result.json.tmp.$$"
  mv -f -- "$result_root/.control-result.json.tmp.$$" \
    "$result_root/control-result.json"
  sha256sum "$result_root/control-result.json" | awk '{print $1}' \
    >"$result_root/control-result.sha256.tmp"
  mv -f -- "$result_root/control-result.sha256.tmp" \
    "$result_root/control-result.sha256"

  write_root_status 'control-result-ready-for-terminal-classification'
}

verify_control_result() {
  verify_inputs
  [[ -f $result_root/control-result.json &&
     -f $result_root/control-result.sha256 ]] ||
    die 'untreated aggregate result or checksum is absent'
  [[ $(sha256sum "$result_root/control-result.json" | awk '{print $1}') == \
     "$(<"$result_root/control-result.sha256")" ]] ||
    die 'untreated aggregate result changed before terminal classification'
  jq -e \
    --arg run_root "$result_root" \
    --arg vllm "$expected_vllm_head" --arg vllm_tree "$expected_vllm_tree" \
    --arg kernel "$expected_kernel_head" --arg kernel_tree "$expected_kernel_tree" \
    --arg base "$expected_base_digest" --arg image "$expected_both_image_id" \
    --arg receipt "$expected_receipt_sha256" \
    --arg lab_head "$(<"$inputs/lab-head.txt")" \
    --arg host_kernel "$expected_host_kernel" --arg boot_id "$expected_host_boot_id" \
    --arg inputs_manifest "$frozen_inputs_manifest_sha256" \
    --arg cache_manifest "$frozen_control_cache_manifest_sha256" \
    --argjson diagnostic_floor "$diagnostic_floor" \
    --argjson strict_floor "$strict_floor" '
    .schema == "neural-download-current-main-tp1-untreated-control-result-v1" and
    .state == "complete" and .run_root == $run_root and
    .identity.vllm_head == $vllm and .identity.vllm_tree == $vllm_tree and
    .identity.kernel_head == $kernel and .identity.kernel_tree == $kernel_tree and
    .identity.base_digest == $base and .identity.image_id == $image and
    .identity.receipt_sha256 == $receipt and .identity.lab_head == $lab_head and
    .host.kernel == $host_kernel and .host.boot_id == $boot_id and
    .floors_tok_s.diagnostic == $diagnostic_floor and
    .floors_tok_s.strict == $strict_floor and
    (.qualification_ready | type) == "boolean" and
    (.evidence.all_non_speed_gates_pass | type) == "boolean" and
    .evidence.postreboot_hardware_gate_pass == true and
    .evidence.frozen_inputs_manifest_sha256 == $inputs_manifest and
    .evidence.compiled_cache_manifest_sha256 == $cache_manifest
  ' "$result_root/control-result.json" >/dev/null ||
    die 'untreated aggregate result failed terminal identity validation'
}

run_control_fresh
run_control_replay_a
run_control_replay_b
verify_control_result

qualification_ready=$(jq -r '.qualification_ready' "$result_root/control-result.json")
all_non_speed=$(jq -r '.evidence.all_non_speed_gates_pass'   "$result_root/control-result.json")
if [[ $qualification_ready == true ]]; then
  terminal_state=pass-untreated-current-base
  terminal_rc=0
elif [[ $all_non_speed == true ]]; then
  terminal_state=complete-speed-only-regression-no-overlay-run
  terminal_rc=10
else
  terminal_state=control-non-speed-failure
  terminal_rc=11
fi
trap '' INT TERM HUP
seal_campaign_status "$terminal_state"
trap - EXIT
exit "$terminal_rc"
