#!/usr/bin/env bash
set -euo pipefail

# Closed 0ecc qualification program retained as an exact historical template.
# Live source-recency checks make it non-runnable after upstream advanced. A
# new source identity must use a separately versioned packet and preregistration.

mode=${1:-all}
[[ $mode == all ]] || {
  printf 'usage: %s all\n' "$0" >&2
  printf 'record-grade qualification is atomic and cannot resume individual arms\n' >&2
  exit 2
}

script_path=$(realpath -e -- "${BASH_SOURCE[0]}")
script_dir=$(dirname -- "$script_path")
repo=$(git -C "$script_dir" rev-parse --show-toplevel)
runner=$repo/experiments/qwen38-27b-b70/scripts/run-20260823-qwen38-absolute-current-main-strict-smoke.sh
receipt=$repo/experiments/qwen38-27b-b70/data/2026-08-23-qwen38-absolute-current-main-build.json
suite=$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json
baseline=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json
model_manifest=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json
model_verifier=$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py
bench_helper=$repo/scripts/bench-openai-realistic-suite.py
quality_helper=$repo/scripts/qwen38-text-quality-suite.py
overlay=$repo/experiments/qwen38-27b-b70/autotune-winner-overlays/tp1-0ecc-stock-kernel-best-config-candidate
seed_source=$overlay/source
overlay_manifest=$overlay/manifest.sha256
overlay_metadata=$overlay/metadata.json
overlay_readme=$overlay/README.md
prereg=$repo/experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-0ecc-tp1-control-decision-overlay-prereg.md
hardware_gate_runner=$repo/experiments/qwen38-27b-b70/scripts/run-20260824-qwen38-postreboot-hardware-gate.sh
hardware_gate=/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-20260824-086de284
result_root=${RESULT_ROOT:-/home/steve/qwen38-current-main-runs/tp1-control-decision-overlay-0ecc-20260824}
inputs=$result_root/inputs
control_cache=$result_root/control-cache
overlay_cache=$result_root/overlay-cache
control_fresh_out=$result_root/control-fresh-diagnostic
control_replay_a_out=$result_root/control-strict-quality-replay-a
control_replay_b_out=$result_root/control-strict-replay-b
fresh_out=$result_root/seeded-fresh-diagnostic
replay_a_out=$result_root/strict-quality-replay-a
replay_b_out=$result_root/strict-replay-b
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}

expected_suite_sha256=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
expected_baseline_sha256=738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18
expected_receipt_sha256=275029980b9c1b59b341ca8a2e2ca1d8845505f74e700cc9e653635c1bb96947
expected_metadata_sha256=d62710d6b03d0bd39c6ac756ee594de3c3066e0e7317d765e546c0cd34b4790b
expected_prereg_sha256=4a5a9c35eefe70fcfddb3ffeff774fc48370907391a2b4264b8932440ebed3a2
expected_seed_manifest_sha256=b941bb71c1d264dcd55104b106b2dff6a85c686776b072e0ef6cc18a8354c928
expected_seed_count=38
expected_vllm_head=0ecc284790e5403f74b899524ef82ecb69f83cb3
expected_vllm_tree=942cc5fd4d0ae008499926a1949630f627b87f71
expected_kernel_head=baaa05bb4e92901219a5a072dd63f2474896f6d1
expected_kernel_tree=e7e7d1063f232a383c98c1820cebb94c45b4906e
expected_base_digest=sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876
expected_both_image_id=sha256:b44e0658393e5a57f8af7173e9f42c7498763b9b581a57cba0f5ce5b8a597728
expected_host_kernel=7.0.0-30-generic
expected_outer_namespace=d65565f7e2
expected_aot_namespace=68fc8c632858eb7c65d6de5b3d4f347cb96e1b18357ec6468847d6c7010adc9d
expected_code_hash=fb13d4aa1ef8a386c76ab56d39925ff4de083895d9dcbd136e778046e78bb118
expected_compiler_hash=ddcad03736
expected_config_hash=7fd9f3bcb2
expected_env_sha256=58a8631879b3855c3c1a408d3dad33d48f66b17f7541f08d51d3f1030d7baceb
expected_graph_sha256=f493f62d98181193e6760136123c70511e9a0a7f1d91cbf3243008a619553339
diagnostic_floor=30.2178
strict_floor=30.31067504052998

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

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
    --arg boot_id "$(</proc/sys/kernel/random/boot_id)" \
    --arg kernel "$expected_host_kernel" \
    --arg repo_head "$(git -C "$repo" rev-parse HEAD)" '
    .passed == true and .host.boot_id == $boot_id and .host.kernel == $kernel and
    .host.taint_pre == "0" and .host.taint_post == "0" and
    .repo_head == $repo_head and .gates.four_device_identity == true and
    .gates.per_card_compute == true and .gates.four_device_peer_read == true and
    .gates.four_rank_xccl_allreduce == true and .gates.repo_postflight == true and
    .gates.atomic_lock_handoff == true and
    .gates.selector_and_mask_combined == false and
    .gates.kernel_reject_events == 0
  ' "$hardware_gate/summary.json" >/dev/null ||
    die 'post-reboot hardware gate is not valid for this commit and boot'
}

for required in "$runner" "$receipt" "$suite" "$baseline" \
  "$model_manifest" "$model_verifier" "$bench_helper" "$quality_helper" \
  "$overlay_manifest" "$overlay_metadata" "$overlay_readme" "$prereg" \
  "$hardware_gate_runner"; do
  [[ -e $required ]] || die "missing input: $required"
done
[[ -d $seed_source ]] || die "missing seed bundle: $seed_source"
[[ -r $sudo_pass_file ]] || die 'sudo password file is unreadable'
[[ $(sha256sum "$suite" | awk '{print $1}') == "$expected_suite_sha256" ]] ||
  die 'validation suite hash changed'
[[ $(sha256sum "$baseline" | awk '{print $1}') == "$expected_baseline_sha256" ]] ||
  die 'quality baseline hash changed'
[[ $(sha256sum "$receipt" | awk '{print $1}') == "$expected_receipt_sha256" ]] ||
  die 'exact 0ecc build receipt changed'
[[ $(sha256sum "$overlay_metadata" | awk '{print $1}') == \
   "$expected_metadata_sha256" ]] || die 'overlay metadata hash changed'
[[ $(sha256sum "$prereg" | awk '{print $1}') == "$expected_prereg_sha256" ]] ||
  die 'overlay preregistration hash changed'
[[ $(sha256sum "$overlay_manifest" | awk '{print $1}') == \
   "$expected_seed_manifest_sha256" ]] || die 'overlay manifest hash changed'
[[ $(find "$seed_source" -type f | wc -l) == "$expected_seed_count" ]] ||
  die 'overlay seed file count changed'
[[ -z $(find "$seed_source" -type l -print -quit) ]] ||
  die 'overlay seed contains a symlink'
(
  cd "$seed_source"
  sha256sum -c ../manifest.sha256 >/dev/null
) || die 'overlay seed checksum failure'
jq -e --arg vllm "$expected_vllm_head" \
  --arg kernel "$expected_kernel_head" \
  --arg manifest "$expected_seed_manifest_sha256" '
  .state == "stale-before-launch" and .closure.executed_arms == 0 and
  .target.vllm_head == $vllm and .target.kernel_head == $kernel and
  .bundle.file_count == 38 and .bundle.manifest_sha256 == $manifest and
  .bundle.compiled_binaries_included == false and
  .bundle.generated_kernels_included == false and
  .bundle.aot_model_included == false and
  .compatibility.configs_hash_mismatches == 0 and
  .compatibility.normalized_decisions_different == 17 and
  .host_transition.postreboot_hardware_gate_required == true and
  .host_transition.same_boot_untreated_control_required == true and
  .host_transition.overlay_forbidden_if_untreated_control_passes == true and
  .qualification_rule.same_boot_untreated_control_arms == 3 and
  .qualification_rule.decision_overlay_arms_only_after_control_speed_miss == 3
' "$overlay_metadata" >/dev/null || die 'overlay metadata contract changed'
jq -e \
  --arg vllm "$expected_vllm_head" --arg vllm_tree "$expected_vllm_tree" \
  --arg kernel "$expected_kernel_head" --arg kernel_tree "$expected_kernel_tree" \
  --arg base "$expected_base_digest" --arg image "$expected_both_image_id" '
  .schema == "neural-download-absolute-current-main-build-v1" and
  .state == "static-preflight-passed-for-built-images-gpu-qualification-pending" and
  .mode == "--build-all" and .overlay == "none" and
  .vllm.head == $vllm and .vllm.tree == $vllm_tree and
  .kernel.head == $kernel and .kernel.tree == $kernel_tree and
  .base_digest == $base and
  .images.both_current_zero_overlay.built == true and
  .images.both_current_zero_overlay.image_id == $image and
  .images.both_current_zero_overlay.static_preflight_passed == true
' "$receipt" >/dev/null || die 'exact 0ecc build receipt contract changed'
die 'the 0ecc qualification program is closed stale before launch; derive a separately versioned current-source packet'
[[ $(uname -r) == "$expected_host_kernel" ]] ||
  die "host kernel changed: $(uname -r)"
for command_name in awk docker flock git jq realpath sha256sum sudo timeout; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done
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

acquire_campaign_locks
RESULT_ROOT="$hardware_gate" SUDO_PASS_FILE="$sudo_pass_file" \
QWEN_CURRENT_MUSE_LOCK_FD="$campaign_muse_lock_fd" \
QWEN_CURRENT_HOST_LOCK_FD="$campaign_host_lock_fd" \
QWEN_CURRENT_GPU_LEASE_FDS="$campaign_gpu_lease_csv" \
  "$hardware_gate_runner"
validate_hardware_gate

prepare_inputs() {
  [[ ! -e $result_root ]] || die "result root already exists: $result_root"
  mkdir -p -- "$inputs/decision-seed"
  cp --reflink=never -- "$runner" "$inputs/strict-smoke.sh"
  cp --reflink=never -- "$script_path" "$inputs/overlay-runner.sh"
  cp --reflink=never -- "$receipt" "$inputs/build-receipt.json"
  cp --reflink=never -- "$suite" "$inputs/validation-suite.json"
  cp --reflink=never -- "$baseline" "$inputs/quality-baseline.json"
  cp --reflink=never -- "$model_manifest" "$inputs/model-manifest.json"
  cp --reflink=never -- "$model_verifier" "$inputs/verify-model-direct.py"
  cp --reflink=never -- "$bench_helper" "$inputs/bench-openai-realistic-suite.py"
  cp --reflink=never -- "$quality_helper" "$inputs/qwen38-text-quality-suite.py"
  cp --reflink=never -- "$overlay_manifest" "$inputs/decision-seed-manifest.sha256"
  cp --reflink=never -- "$overlay_metadata" "$inputs/decision-overlay-metadata.json"
  cp --reflink=never -- "$overlay_readme" "$inputs/decision-overlay-README.md"
  cp --reflink=never -- "$prereg" "$inputs/preregistration.md"
  cp --reflink=never -- "$hardware_gate/summary.json" \
    "$inputs/postreboot-hardware-gate-summary.json"
  cp --reflink=never -- "$hardware_gate/final.status" \
    "$inputs/postreboot-hardware-gate-final.status"
  cp --reflink=never -- "$hardware_gate/SHA256SUMS" \
    "$inputs/postreboot-hardware-gate-SHA256SUMS"
  while IFS= read -r -d '' seed_file; do
    relative=${seed_file#"$seed_source"/}
    mkdir -p -- "$inputs/decision-seed/$(dirname -- "$relative")"
    cp --reflink=never -- "$seed_file" "$inputs/decision-seed/$relative"
  done < <(find "$seed_source" -type f -name '*.best_config' -print0 | sort -z)
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
  chmod 0555 "$inputs/strict-smoke.sh" "$inputs/overlay-runner.sh" \
    "$inputs/verify-model-direct.py"
  find "$inputs" -type f ! -perm /111 -exec chmod 0444 {} +
  verify_inputs
}

verify_inputs() {
  [[ -d $inputs ]] || die 'frozen input directory is absent'
  (
    cd "$inputs"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die 'frozen input snapshot changed'
  cmp -s "$script_path" "$inputs/overlay-runner.sh" ||
    die 'live wrapper differs from frozen wrapper'
  [[ $(<"$inputs/host-kernel-release.txt") == "$expected_host_kernel" ]] ||
    die 'frozen host kernel is not the preregistered kernel'
  [[ $(uname -r) == "$(<"$inputs/host-kernel-release.txt")" ]] ||
    die 'host kernel changed between overlay arms'
  uname -a | cmp -s - "$inputs/host-uname.txt" ||
    die 'host uname changed between overlay arms'
  cmp -s /proc/sys/kernel/random/boot_id "$inputs/host-boot-id.txt" ||
    die 'host rebooted between overlay arms'
  cmp -s /proc/cmdline "$inputs/host-cmdline.txt" ||
    die 'host command line changed between overlay arms'
  cmp -s "$hardware_gate/SHA256SUMS" \
    "$inputs/postreboot-hardware-gate-SHA256SUMS" ||
    die 'post-reboot hardware-gate manifest changed between arms'
  (
    cd "$hardware_gate"
    sha256sum -c "$inputs/postreboot-hardware-gate-SHA256SUMS" >/dev/null
  ) || die 'post-reboot hardware-gate evidence changed between arms'
  cmp -s "$hardware_gate/summary.json" \
    "$inputs/postreboot-hardware-gate-summary.json" ||
    die 'post-reboot hardware-gate summary changed between arms'
  cmp -s "$hardware_gate/final.status" \
    "$inputs/postreboot-hardware-gate-final.status" ||
    die 'post-reboot hardware-gate status changed between arms'
  live_lab_status=$(git -C "$repo" status --porcelain=v1 --untracked-files=all) ||
    die 'lab repository status check failed between overlay arms'
  [[ -z $live_lab_status ]] ||
    die 'lab repository became dirty between overlay arms'
  [[ $(git -C "$repo" branch --show-current) == main ]] ||
    die 'lab repository left main between overlay arms'
  frozen_lab_head=$(<"$inputs/lab-head.txt")
  [[ $(git -C "$repo" rev-parse HEAD) == "$frozen_lab_head" ]] ||
    die 'lab commit changed between overlay arms'
  [[ $(git -C "$repo" rev-parse origin/main) == "$frozen_lab_head" ]] ||
    die 'local origin/main changed between overlay arms'
  live_lab_head=$(timeout --signal=TERM --kill-after=5s 30s \
    git -C "$repo" ls-remote --exit-code origin refs/heads/main |
    awk 'NR == 1 {print $1}')
  [[ $live_lab_head == "$frozen_lab_head" ]] ||
    die 'live lab origin/main changed between overlay arms'
  live_vllm_head=$(timeout --signal=TERM --kill-after=5s 30s git ls-remote --exit-code \
    https://github.com/vllm-project/vllm.git refs/heads/main |
    awk 'NR == 1 {print $1}')
  [[ $live_vllm_head == "$expected_vllm_head" ]] ||
    die 'vLLM main advanced during overlay qualification'
  live_kernel_head=$(timeout --signal=TERM --kill-after=5s 30s git ls-remote --exit-code \
    https://github.com/vllm-project/vllm-xpu-kernels.git refs/heads/main |
    awk 'NR == 1 {print $1}')
  [[ $live_kernel_head == "$expected_kernel_head" ]] ||
    die 'XPU-kernel main advanced during overlay qualification'
  live_base_digest=$(timeout --signal=TERM --kill-after=5s 60s \
    sudo -S -p '' docker buildx imagetools inspect \
    vllm/vllm-openai-xpu:nightly --format '{{.Manifest.Digest}}' \
    <"$sudo_pass_file")
  [[ $live_base_digest == "$expected_base_digest" ]] ||
    die 'official nightly base advanced during overlay qualification'
  sudo -S -p '' docker image inspect "$expected_both_image_id" \
    >/dev/null <"$sudo_pass_file" || die 'exact current image is absent'
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

root_exit() {
  local rc=$?
  trap - EXIT
  trap '' INT TERM HUP
  if [[ $rc -ne 0 && -d $result_root ]]; then
    set +e
    root_state=$(read_status_or_missing "$result_root/final.status")
    case $root_state in
      control-non-speed-failure|complete-regression-not-recovered) ;;
      *)
        printf 'failed-incomplete mode=%s rc=%s\n' "$mode" "$rc" \
          >"$result_root/final.status"
        root_state=$(read_status_or_missing "$result_root/final.status")
        ;;
    esac
    jq -n \
      --arg state "$root_state" --arg mode "$mode" --argjson rc "$rc" \
      --arg host_kernel "$(uname -r)" \
      --arg boot_id "$(</proc/sys/kernel/random/boot_id)" \
      --arg control_fresh_status "$(read_status_or_missing "$control_fresh_out/final.status")" \
      --arg control_replay_a_status "$(read_status_or_missing "$control_replay_a_out/final.status")" \
      --arg control_replay_b_status "$(read_status_or_missing "$control_replay_b_out/final.status")" \
      --arg fresh_status "$(read_status_or_missing "$fresh_out/final.status")" \
      --arg replay_a_status "$(read_status_or_missing "$replay_a_out/final.status")" \
      --arg replay_b_status "$(read_status_or_missing "$replay_b_out/final.status")" \
      --argjson control_diagnostic_median "$(read_median_or_null "$control_fresh_out/bench.json")" \
      --argjson control_strict_a_median "$(read_median_or_null "$control_replay_a_out/bench.json")" \
      --argjson control_strict_b_median "$(read_median_or_null "$control_replay_b_out/bench.json")" \
      --argjson diagnostic_median "$(read_median_or_null "$fresh_out/bench.json")" \
      --argjson strict_a_median "$(read_median_or_null "$replay_a_out/bench.json")" \
      --argjson strict_b_median "$(read_median_or_null "$replay_b_out/bench.json")" \
      --arg vllm_head "$expected_vllm_head" \
      --arg kernel_head "$expected_kernel_head" \
      --arg base_digest "$expected_base_digest" \
      --arg image_id "$expected_both_image_id" \
      --arg receipt_sha256 "$expected_receipt_sha256" \
      --arg seed_manifest_sha256 "$expected_seed_manifest_sha256" '{
        schema: "neural-download-current-main-tp1-decision-overlay-failure-v1",
        state: $state,
        mode: $mode,
        exit_code: $rc,
        host: {kernel: $host_kernel, boot_id: $boot_id},
        identity: {
          vllm_head: $vllm_head,
          kernel_head: $kernel_head,
          base_digest: $base_digest,
          image_id: $image_id,
          receipt_sha256: $receipt_sha256,
          seed_manifest_sha256: $seed_manifest_sha256
        },
        arms: {
          control_fresh: {status: $control_fresh_status, median_tok_s: $control_diagnostic_median},
          control_replay_a: {status: $control_replay_a_status, median_tok_s: $control_strict_a_median},
          control_replay_b: {status: $control_replay_b_status, median_tok_s: $control_strict_b_median},
          fresh: {status: $fresh_status, median_tok_s: $diagnostic_median},
          replay_a: {status: $replay_a_status, median_tok_s: $strict_a_median},
          replay_b: {status: $replay_b_status, median_tok_s: $strict_b_median}
        }
      }' >"$result_root/campaign-failure.json"
  fi
  exit "$rc"
}
trap root_exit EXIT

run_clean_env() {
  env -u PYTHONHASHSEED \
    -u VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE \
    -u VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING \
    -u TRITON_CACHE_AUTOTUNING -u VLLM_XPU_ENABLE_XPU_GRAPH \
    -u EXTRA_VLLM_ARGS -u PROMPT_IDS -u ONEAPI_DEVICE_SELECTOR \
    -u ZE_AFFINITY_MASK -u XPU_GRAPH -u COMPILATION_CONFIG \
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

run_control_fresh() {
  prepare_inputs
  verify_inputs
  run_clean_env "${common_env[@]}" \
    CACHE_POLICY=fresh NATURAL_EOS=0 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19761 \
      "$control_fresh_out" "$inputs/validation-suite.json" "$control_cache"
  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$control_fresh_out/bench.json")
  write_speed_gate "$control_fresh_out/current-base-speed-gate.status" \
    "$actual" "$diagnostic_floor"
  verify_inputs
  printf 'control-fresh-complete-awaiting-replay-a\n' >"$result_root/final.status"
}

require_control_fresh() {
  verify_inputs
  [[ $(<"$control_fresh_out/final.status") == pass ]] ||
    die 'untreated control fresh arm did not pass its non-speed gates'
  grep -Eq '^(pass|fail) ' "$control_fresh_out/current-base-speed-gate.status" ||
    die 'untreated control fresh speed gate is absent'
}

run_control_replay_a() {
  require_control_fresh
  control_cache_manifest_sha=$(<"$control_fresh_out/cache-manifest.post.sha256.digest")
  run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay EXPECTED_CACHE_MANIFEST_SHA256="$control_cache_manifest_sha" \
    NATURAL_EOS=1 QUALITY=1 QUALITY_REQUIRE_BASELINE=1 \
    QUALITY_BASELINE_JSON="$inputs/quality-baseline.json" \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19762 \
      "$control_replay_a_out" "$inputs/validation-suite.json" "$control_cache"
  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$control_replay_a_out/bench.json")
  write_speed_gate "$control_replay_a_out/current-base-strict-a-gate.status" \
    "$actual" "$strict_floor"
  verify_inputs
  printf 'control-replay-a-complete-awaiting-replay-b\n' \
    >"$result_root/final.status"
}

require_control_replay_a() {
  require_control_fresh
  [[ $(<"$control_replay_a_out/final.status") == pass ]] ||
    die 'untreated control replay A did not pass its non-speed gates'
  grep -Eq '^(pass|fail) ' \
    "$control_replay_a_out/current-base-strict-a-gate.status" ||
    die 'untreated control replay A speed gate is absent'
}

run_control_replay_b() {
  require_control_replay_a
  control_cache_manifest_sha=$(<"$control_fresh_out/cache-manifest.post.sha256.digest")
  run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay EXPECTED_CACHE_MANIFEST_SHA256="$control_cache_manifest_sha" \
    NATURAL_EOS=1 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19763 \
      "$control_replay_b_out" "$inputs/validation-suite.json" "$control_cache"
  [[ $(<"$control_replay_b_out/final.status") == pass ]] ||
    die 'untreated control replay B did not pass its non-speed gates'
  actual_b=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$control_replay_b_out/bench.json")
  write_speed_gate "$control_replay_b_out/current-base-strict-b-gate.status" \
    "$actual_b" "$strict_floor"
  verify_inputs

  control_inputs_manifest_sha256=$(sha256sum "$inputs/SHA256SUMS" |
    awk '{print $1}')
  control_cache_manifest_sha=$(<"$control_fresh_out/cache-manifest.post.sha256.digest")
  control_replay_a_cache_immutable=false
  cmp -s "$control_replay_a_out/cache-manifest.pre.sha256" \
    "$control_replay_a_out/cache-manifest.post.sha256" &&
    control_replay_a_cache_immutable=true
  control_replay_b_cache_immutable=false
  cmp -s "$control_replay_b_out/cache-manifest.pre.sha256" \
    "$control_replay_b_out/cache-manifest.post.sha256" &&
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
      role: "same-boot fresh untreated control before any decision overlay",
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
  ' >"$result_root/control-result.json"
  sha256sum "$result_root/control-result.json" | awk '{print $1}' \
    >"$result_root/control-result.sha256.tmp"
  mv -f -- "$result_root/control-result.sha256.tmp" \
    "$result_root/control-result.sha256"

  if [[ $(jq -r .qualification_ready "$result_root/control-result.json") == true ]]; then
    printf 'pass-untreated-current-base\n' >"$result_root/final.status"
  elif [[ $(jq -r .evidence.all_non_speed_gates_pass \
      "$result_root/control-result.json") != true ]]; then
    printf 'control-non-speed-failure\n' >"$result_root/final.status"
    die 'untreated control failed a non-speed qualification gate'
  else
    printf 'control-speed-regression-overlay-required\n' \
      >"$result_root/final.status"
  fi
}

validate_control_regression() {
  verify_inputs
  [[ -f $result_root/control-result.sha256 ]] ||
    die 'same-boot untreated control result checksum is absent'
  [[ $(sha256sum "$result_root/control-result.json" | awk '{print $1}') == \
     "$(<"$result_root/control-result.sha256")" ]] ||
    die 'same-boot untreated control result changed before or during overlay arms'
  jq -e \
    --arg vllm "$expected_vllm_head" --arg kernel "$expected_kernel_head" \
    --arg image "$expected_both_image_id" \
    --arg boot_id "$(</proc/sys/kernel/random/boot_id)" '
    .schema == "neural-download-current-main-tp1-untreated-control-result-v1" and
    .state == "complete" and .qualification_ready == false and
    .evidence.all_non_speed_gates_pass == true and
    .identity.vllm_head == $vllm and .identity.kernel_head == $kernel and
    .identity.image_id == $image and .host.boot_id == $boot_id
  ' "$result_root/control-result.json" >/dev/null ||
    die 'same-boot untreated control result is not a valid overlay prerequisite'
}

require_control_regression() {
  validate_control_regression
  [[ $(<"$result_root/final.status") == control-speed-regression-overlay-required ]] ||
    die 'decision overlay is forbidden unless the same-boot untreated control misses'
}

run_overlay_fresh() {
  require_control_regression
  run_clean_env "${common_env[@]}" \
    CACHE_POLICY=seeded-fresh \
    BEST_CONFIG_SEED_DIR="$inputs/decision-seed" \
    EXPECTED_BEST_CONFIG_SEED_COUNT="$expected_seed_count" \
    EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256="$expected_seed_manifest_sha256" \
    BEST_CONFIG_TARGET_AOT_NAMESPACE="$expected_aot_namespace" \
    EXPECTED_CACHE_OUTER_NAMESPACE="$expected_outer_namespace" \
    EXPECTED_CACHE_CODE_HASH="$expected_code_hash" \
    EXPECTED_CACHE_COMPILER_HASH="$expected_compiler_hash" \
    EXPECTED_CACHE_CONFIG_HASH="$expected_config_hash" \
    EXPECTED_CACHE_ENV_SHA256="$expected_env_sha256" \
    EXPECTED_COMPUTATION_GRAPH_SHA256S="$expected_graph_sha256" \
    NATURAL_EOS=0 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19764 \
      "$fresh_out" "$inputs/validation-suite.json" "$overlay_cache"
  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$fresh_out/bench.json")
  if awk -v actual="$actual" -v floor="$diagnostic_floor" \
      'BEGIN {exit !(actual >= floor)}'; then
    printf 'pass actual=%s floor=%s\n' "$actual" "$diagnostic_floor" \
      >"$fresh_out/overlay-speed-gate.status"
  else
    printf 'fail actual=%s floor=%s\n' "$actual" "$diagnostic_floor" \
      >"$fresh_out/overlay-speed-gate.status"
    die "seeded diagnostic missed at $actual tok/s"
  fi
  verify_inputs
  printf 'fresh-pass-awaiting-replay-a\n' >"$result_root/final.status"
}

require_overlay_fresh() {
  validate_control_regression
  [[ $(<"$fresh_out/final.status") == pass ]] || die 'fresh arm did not pass'
  grep -q '^pass ' "$fresh_out/overlay-speed-gate.status" ||
    die 'fresh speed gate did not pass'
}

run_overlay_replay_a() {
  require_overlay_fresh
  cache_manifest_sha=$(<"$fresh_out/cache-manifest.post.sha256.digest")
  run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay EXPECTED_CACHE_MANIFEST_SHA256="$cache_manifest_sha" \
    NATURAL_EOS=1 QUALITY=1 QUALITY_REQUIRE_BASELINE=1 \
    QUALITY_BASELINE_JSON="$inputs/quality-baseline.json" \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19765 \
      "$replay_a_out" "$inputs/validation-suite.json" "$overlay_cache"
  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$replay_a_out/bench.json")
  if awk -v actual="$actual" -v floor="$strict_floor" \
      'BEGIN {exit !(actual >= floor)}'; then
    printf 'pass actual=%s floor=%s\n' "$actual" "$strict_floor" \
      >"$replay_a_out/overlay-strict-a-gate.status"
  else
    printf 'fail actual=%s floor=%s\n' "$actual" "$strict_floor" \
      >"$replay_a_out/overlay-strict-a-gate.status"
    die "seeded strict replay A missed at $actual tok/s"
  fi
  verify_inputs
  printf 'replay-a-pass-awaiting-replay-b\n' >"$result_root/final.status"
}

require_overlay_replay_a() {
  require_overlay_fresh
  [[ $(<"$replay_a_out/final.status") == pass ]] || die 'replay A did not pass'
  grep -q '^pass ' "$replay_a_out/overlay-strict-a-gate.status" ||
    die 'replay A speed gate did not pass'
}

run_overlay_replay_b() {
  require_overlay_replay_a
  cache_manifest_sha=$(<"$fresh_out/cache-manifest.post.sha256.digest")
  run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay EXPECTED_CACHE_MANIFEST_SHA256="$cache_manifest_sha" \
    NATURAL_EOS=1 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19766 \
      "$replay_b_out" "$inputs/validation-suite.json" "$overlay_cache"
  [[ $(<"$replay_b_out/final.status") == pass ]] || die 'replay B did not pass'
  validate_control_regression
  actual_a=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$replay_a_out/bench.json")
  actual_b=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$replay_b_out/bench.json")
  inputs_manifest_sha256=$(sha256sum "$inputs/SHA256SUMS" | awk '{print $1}')
  cache_manifest_sha=$(<"$fresh_out/cache-manifest.post.sha256.digest")
  seed_postshutdown_unchanged=false
  if cmp -s "$fresh_out/best-config-seed.source.sha256" \
      "$fresh_out/best-config-seed.postshutdown.sha256"; then
    seed_postshutdown_unchanged=true
  fi
  replay_a_cache_immutable=false
  if cmp -s "$replay_a_out/cache-manifest.pre.sha256" \
      "$replay_a_out/cache-manifest.post.sha256"; then
    replay_a_cache_immutable=true
  fi
  replay_b_cache_immutable=false
  if cmp -s "$replay_b_out/cache-manifest.pre.sha256" \
      "$replay_b_out/cache-manifest.post.sha256"; then
    replay_b_cache_immutable=true
  fi
  source_identity_exact=true
  for arm_out in "$fresh_out" "$replay_a_out" "$replay_b_out"; do
    [[ $(<"$arm_out/upstream-vllm.pre.txt") == "$expected_vllm_head" &&
       $(<"$arm_out/upstream-vllm.post.txt") == "$expected_vllm_head" &&
       $(<"$arm_out/upstream-kernel.pre.txt") == "$expected_kernel_head" &&
       $(<"$arm_out/upstream-kernel.post.txt") == "$expected_kernel_head" &&
       $(<"$arm_out/upstream-nightly-base.pre.txt") == "$expected_base_digest" &&
       $(<"$arm_out/upstream-nightly-base.post.txt") == "$expected_base_digest" ]] ||
      source_identity_exact=false
  done
  jq -n \
    --arg run_root "$result_root" \
    --arg vllm_head "$expected_vllm_head" \
    --arg vllm_tree "$expected_vllm_tree" \
    --arg kernel_head "$expected_kernel_head" \
    --arg kernel_tree "$expected_kernel_tree" \
    --arg base_digest "$expected_base_digest" \
    --arg image_id "$expected_both_image_id" \
    --arg receipt_sha256 "$expected_receipt_sha256" \
    --arg seed_manifest_sha256 "$expected_seed_manifest_sha256" \
    --arg inputs_manifest_sha256 "$inputs_manifest_sha256" \
    --arg cache_manifest_sha256 "$cache_manifest_sha" \
    --arg lab_head "$(<"$inputs/lab-head.txt")" \
    --arg host_kernel "$(<"$inputs/host-kernel-release.txt")" \
    --arg host_uname "$(<"$inputs/host-uname.txt")" \
    --arg host_boot_id "$(<"$inputs/host-boot-id.txt")" \
    --argjson seed_postshutdown_unchanged "$seed_postshutdown_unchanged" \
    --argjson replay_a_cache_immutable "$replay_a_cache_immutable" \
    --argjson replay_b_cache_immutable "$replay_b_cache_immutable" \
    --argjson source_identity_exact "$source_identity_exact" \
    --argjson diagnostic_floor "$diagnostic_floor" \
    --argjson strict_floor "$strict_floor" \
    --slurpfile d "$fresh_out/bench.json" \
    --slurpfile a "$replay_a_out/bench.json" \
    --slurpfile b "$replay_b_out/bench.json" \
    --slurpfile md "$fresh_out/model-direct-and-ordinary-verify.json" \
    --slurpfile ma "$replay_a_out/model-direct-and-ordinary-verify.json" \
    --slurpfile mb "$replay_b_out/model-direct-and-ordinary-verify.json" \
    --slurpfile cd "$fresh_out/canary.json" \
    --slurpfile ca "$replay_a_out/canary.json" \
    --slurpfile cb "$replay_b_out/canary.json" \
    --slurpfile c "$result_root/control-result.json" \
    --slurpfile q "$replay_a_out/quality.json" '
    [range(0; ($a[0].rows | length)) as $i | {
      prompt_id: $a[0].rows[$i].prompt_id,
      prompt_id_matches: ($a[0].rows[$i].prompt_id == $b[0].rows[$i].prompt_id),
      full_token_ids_equal: ($a[0].rows[$i].token_ids == $b[0].rows[$i].token_ids),
      first_100_token_ids_equal: ($a[0].rows[$i].token_ids[:100] == $b[0].rows[$i].token_ids[:100])
    }] as $pairs | {
      schema: "neural-download-current-main-tp1-decision-overlay-result-v1",
      run_root: $run_root,
      state: "complete",
      scope: "cross-boot current-host qualification; not same-boot causal attribution",
      overlay: "38 stock-control best_config candidate decisions; all executables compiled fresh",
      untreated_control: {
        qualification_ready: $c[0].qualification_ready,
        medians_tok_s: $c[0].medians_tok_s,
        speed_gates: $c[0].speed_gates,
        all_non_speed_gates_pass: $c[0].evidence.all_non_speed_gates_pass,
        same_host_boot: ($c[0].host.boot_id == $host_boot_id)
      },
      identity: {
        vllm_head: $vllm_head,
        vllm_tree: $vllm_tree,
        kernel_head: $kernel_head,
        kernel_tree: $kernel_tree,
        base_digest: $base_digest,
        image_id: $image_id,
        receipt_sha256: $receipt_sha256,
        lab_head: $lab_head
      },
      host: {
        kernel: $host_kernel,
        uname: $host_uname,
        boot_id: $host_boot_id,
        same_boot_for_all_arms: true
      },
      evidence: {
        frozen_inputs_manifest_sha256: $inputs_manifest_sha256,
        decision_seed_manifest_sha256: $seed_manifest_sha256,
        compiled_cache_manifest_sha256: $cache_manifest_sha256,
        seed_unchanged_after_container_shutdown: $seed_postshutdown_unchanged,
        replay_a_full_cache_immutable: $replay_a_cache_immutable,
        replay_b_full_cache_immutable: $replay_b_cache_immutable,
        exact_source_identity_pre_and_post_all_arms: $source_identity_exact,
        arm_final_statuses_pass: true,
        repo_and_host_postflight_pass: true,
        model_identity_all_arms: (
          $md[0].status == "verified" and ($md[0].files | length) == 19 and
          all($md[0].files[]; .ok == true) and
          $ma[0].status == "verified" and ($ma[0].files | length) == 19 and
          all($ma[0].files[]; .ok == true) and
          $mb[0].status == "verified" and ($mb[0].files | length) == 19 and
          all($mb[0].files[]; .ok == true)
        ),
        canary_all_arms: (
          $cd[0].content == "14" and $cd[0].cached_tokens == 0 and
          $ca[0].content == "14" and $ca[0].cached_tokens == 0 and
          $cb[0].content == "14" and $cb[0].cached_tokens == 0
        ),
        realistic_benchmark_all_arms: (
          $d[0].realistic_final_gate.passed == true and
          $a[0].realistic_final_gate.passed == true and
          $b[0].realistic_final_gate.passed == true and
          $d[0].fresh_response_validity.cached_tokens_all_zero == true and
          $a[0].fresh_response_validity.cached_tokens_all_zero == true and
          $b[0].fresh_response_validity.cached_tokens_all_zero == true
        )
      },
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
      replay_token_comparison: {
        prompt_count: ($pairs | length),
        prompt_order_matches: (all($pairs[]; .prompt_id_matches)),
        full_token_array_matches: ([$pairs[] | select(.full_token_ids_equal)] | length),
        first_100_token_array_matches: ([$pairs[] | select(.first_100_token_ids_equal)] | length),
        rows: $pairs
      },
      quality: {
        pass_all: $q[0].pass_all,
        baseline_match_all: $q[0].baseline_match_all,
        exact_cases: ($q[0].exact_cases | length),
        repeat_runs: ($q[0].repeat_case.runs | length),
        long_context_tokens: $q[0].long_context_case.requested_context_tokens,
        long_context_actual_prompt_tokens: $q[0].long_context_case.actual_prompt_tokens,
        baseline_comparisons: ($q[0].baseline_comparisons | length)
      },
      qualification_ready: (
        $c[0].qualification_ready == false and
        $c[0].evidence.all_non_speed_gates_pass == true and
        $c[0].host.boot_id == $host_boot_id and
        $d[0].summary.tok_s_1_100_intervals_after_ttft.median >= $diagnostic_floor and
        $a[0].summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor and
        $b[0].summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor and
        $q[0].pass_all == true and $q[0].baseline_match_all == true and
        ($q[0].exact_cases | length) == 7 and
        ($q[0].repeat_case.runs | length) == 8 and
        $q[0].long_context_case.requested_context_tokens == 8192 and
        $q[0].long_context_case.actual_prompt_tokens == 7617 and
        ($q[0].baseline_comparisons | length) == 24 and
        $seed_postshutdown_unchanged and
        $replay_a_cache_immutable and $replay_b_cache_immutable and
        $source_identity_exact and
        $md[0].status == "verified" and ($md[0].files | length) == 19 and
        all($md[0].files[]; .ok == true) and
        $ma[0].status == "verified" and ($ma[0].files | length) == 19 and
        all($ma[0].files[]; .ok == true) and
        $mb[0].status == "verified" and ($mb[0].files | length) == 19 and
        all($mb[0].files[]; .ok == true) and
        $cd[0].content == "14" and $cd[0].cached_tokens == 0 and
        $ca[0].content == "14" and $ca[0].cached_tokens == 0 and
        $cb[0].content == "14" and $cb[0].cached_tokens == 0 and
        $d[0].realistic_final_gate.passed == true and
        $a[0].realistic_final_gate.passed == true and
        $b[0].realistic_final_gate.passed == true and
        all($pairs[]; .prompt_id_matches)
      )
    }' >"$result_root/campaign-result.json"
  if [[ $(jq -r .qualification_ready "$result_root/campaign-result.json") == true ]]; then
    printf 'pass actual_a=%s actual_b=%s floor=%s\n' \
      "$actual_a" "$actual_b" "$strict_floor" \
      >"$replay_b_out/overlay-stability-gate.status"
    printf 'pass\n' >"$result_root/final.status"
  else
    printf 'fail actual_a=%s actual_b=%s floor=%s\n' \
      "$actual_a" "$actual_b" "$strict_floor" \
      >"$replay_b_out/overlay-stability-gate.status"
    printf 'complete-regression-not-recovered\n' >"$result_root/final.status"
    die "seeded strict stability missed at $actual_a / $actual_b tok/s"
  fi
}

case $mode in
  all)
    run_control_fresh
    run_control_replay_a
    run_control_replay_b
    if [[ $(jq -r .qualification_ready "$result_root/control-result.json") == false ]]; then
      run_overlay_fresh
      run_overlay_replay_a
      run_overlay_replay_b
    fi
    ;;
  control-fresh) run_control_fresh ;;
  control-replay-a) run_control_replay_a ;;
  control-replay-b) run_control_replay_b ;;
  overlay-fresh) run_overlay_fresh ;;
  overlay-replay-a) run_overlay_replay_a ;;
  overlay-replay-b) run_overlay_replay_b ;;
esac
