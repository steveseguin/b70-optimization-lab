#!/usr/bin/env bash
set -Eeuo pipefail

# Atomic, untreated-first TP1 qualification r1 for literal-current vLLM
# d154d90d6c and exact-current XPU kernel baaa. This separately named successor
# carries the audited narrow fail-closed classifier and current SMART/ext4
# proof forward without a decision, source, DSO, binary, generated-kernel, or
# prior-cache overlay.

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
runner=$repo/experiments/qwen38-27b-b70/scripts/run-20260824-qwen38-known-nvme-aware-strict-smoke.sh
kernel_delta_classifier=$repo/experiments/qwen38-27b-b70/scripts/classify-20260824-kernel-delta.py
kernel_delta_classifier_test=$repo/experiments/qwen38-27b-b70/tests/test_classify_20260824_kernel_delta.py
classifier_test_python=/home/steve/.venvs/vllm-xpu/bin/python
receipt=$repo/experiments/qwen38-27b-b70/data/2026-08-24-qwen38-d154d90d6c-absolute-current-main-build.json
suite=$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json
baseline=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json
model_manifest=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json
model_verifier=$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py
bench_helper=$repo/scripts/bench-openai-realistic-suite.py
quality_helper=$repo/scripts/qwen38-text-quality-suite.py
prereg=$repo/experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-d154d90d6c-untreated-tp1-r1-prereg.md
hardware_gate_runner=$repo/experiments/qwen38-27b-b70/scripts/run-20260824-qwen38-known-nvme-aware-hardware-gate.sh
build_script=$repo/experiments/qwen38-27b-b70/scripts/build-20260823-qwen38-absolute-current-main-images.sh
build_dockerfile=$repo/experiments/qwen38-27b-b70/docker/Dockerfile.absolute-current-main
lane_root=$repo/experiments/qwen38-27b-b70
protected_manifest=$lane_root/data/2026-08-23-qwen38-current-main-overlay-manifest.json
tp2_overlay=$lane_root/autotune-winner-overlays/tp2-e9d1398-best-config
tp4_overlay=$lane_root/autotune-winner-overlays/tp4-e9d1398-best-config
predecessor_6a9_record=$lane_root/data/2026-08-24-qwen38-6a9c69fa85-tp1-r1-speed-only-miss.json
predecessor_6a9_note=$lane_root/notes/2026-08-24-qwen38-6a9c69fa85-tp1-r1-speed-only-miss.md
predecessor_342_record=$lane_root/data/2026-08-24-qwen38-342b8ebd8b-r2-stale-before-launch.json
predecessor_342_note=$lane_root/notes/2026-08-24-qwen38-342b8ebd8b-r2-stale-before-launch.md
predecessor_0d7_record=$lane_root/data/2026-08-24-qwen38-0d7d5ed0b2-r1-stale-before-launch.json
predecessor_0d7_note=$lane_root/notes/2026-08-24-qwen38-0d7d5ed0b2-r1-stale-before-launch.md
readonly hardware_gate=/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-d154d90d6c-20260824-086de284-venvlib-r1
readonly result_root=/home/steve/qwen38-current-main-runs/tp1-untreated-d154d90d6c-20260824-r1
inputs=$result_root/inputs
control_cache=$result_root/control-cache
control_fresh_out=$result_root/control-fresh-diagnostic
control_replay_a_out=$result_root/control-strict-quality-replay-a
control_replay_b_out=$result_root/control-strict-replay-b
frozen_inputs_manifest_sha256=
frozen_control_cache_manifest_sha256=
frozen_control_cache_directory_manifest_sha256=
classifier_test_receipt=
failure_stage=static-preflight
wrapper_failure_reason=
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}

expected_suite_sha256=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
expected_baseline_sha256=738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18
expected_receipt_sha256=024a1ceb228ff0c60a2ae6ddfe05a23615ba33da3fc05841e8ceb4cf8f694e1e
expected_prereg_sha256=2b13a6b8ad9ed32f444381c6b6735e64862d01c9bc13d10aee6633952f3c3435
expected_runner_sha256=ec86caef12471185b849a91695fd9dd9fa1e4786771b5ee717c40ff2fae24ecb
expected_kernel_delta_classifier_sha256=fef74bdb90b82fdf543be6ea36320b308aff0d0c146a3c92bcbfff334b70d1b0
expected_kernel_delta_classifier_test_sha256=b21befd70003b710027303e093915c36ce88d8fcd4eda66facfd549057e5474b
expected_hardware_gate_runner_sha256=8038015b179048662f53d7d41ead6cddc95671081942444f394c6e48ed57a6f7
expected_model_manifest_sha256=731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
expected_model_verifier_sha256=5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
expected_bench_helper_sha256=442e9777d864f94eca82424929d3875ac15a155fd9e510e5054ef199a9751ab4
expected_quality_helper_sha256=67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d
expected_build_script_sha256=cb1260b00c877420bd847adcebd022504b6ed58643ec8c5740ff8336dd8f549a
expected_build_dockerfile_sha256=440da02c5438ce76da10e49f665ea9bb3dff6cf1a5c5e2accab2b0612e0e6ead
expected_archive_manifest_sha256=3a00ab8f5c35a8086b8e860e6764c67de1a45205c591f69f62baefeaeb34bf6e
expected_source_identity_sha256=a205352f15012a911b9ebc101d78c12d1da03e09cee95ca05dfb0f4bd22bda4c
expected_control_static_preflight_sha256=1e15c2c9d5120f5c69a683d0a5a4b2aa5ef0860d55829255cc25eb9c5c78f42d
expected_both_static_preflight_sha256=729af713ac8546241e76a62a15092235f4e75df4814135dc3f34403d826c3f4a
expected_vllm_wheel_sha256=e1e4d3205987bdb8cc9cd05c99b8bebfd4c1ddbb2c37fb2c4831448710f555fe
expected_vllm_source_archive_sha256=51e428dfe14ca35b06b35812ca8c79599b699a983b8ffa8c08236b88410f8aec
expected_vllm_package_version=0.26.1rc1.dev1161+gd154d90d6.xpu
expected_rust_extension_sha256=7cb3df775d2183d2c1a7d3025a8f49b9a79548d157993969fc0c49f46c725c52
expected_rust_frontend_sha256=a415187153b2a8b10683494c7b22472158b487c69023713313542d4bc09c4c92
expected_batch_invariant_config_path=vllm/model_executor/determinism/batch_invariant_configs.py
expected_batch_invariant_config_sha256=e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128
expected_protected_manifest_sha256=4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454
expected_protected_values_sha256=e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f
expected_tp2_manifest_sha256=65c574c24d24804d250e5179e9a202ec9e77e8c5740cea121b7660d8ee854757
expected_tp2_metadata_sha256=bb46c84ee3a238587957961b7dc7d2a461b5d618489ff8dc362f877c37d3dd63
expected_tp2_readme_sha256=0170d56a4162ac99bafecf7196e2f210cbc57a760041fb5a87fd7a7a568bb574
expected_tp4_manifest_sha256=a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2
expected_tp4_metadata_sha256=f823ef67e40ae8602cc3d16c5e69a1bbbe894a5a019c5fd40275b938c3312cad
expected_tp4_readme_sha256=c2d84ec7c1aff63e659f64f028d938ef0b51bf741f08107f1c64bd828b5c4c4c
expected_predecessor_6a9_record_sha256=5068d6b035deb02395780e5bebf34b6b81082be08029293547acbb4507902784
expected_predecessor_6a9_note_sha256=becac5747b289dfea5923b868ccc26a5589b6d7b525f741d330c6b6f3bf8c3d6
expected_predecessor_342_record_sha256=dee10fae2bad52bdef05c49d7210500839090117160b4ced23f9663452970df8
expected_predecessor_342_note_sha256=2010033f9ce21b73ca35c5994e045cf72462bc3947ddf02df45cdf5d1136e5f5
expected_predecessor_0d7_record_sha256=aa6a2a8731a4cb6fdc620bd7cc5bc8d59e4641775f039471559d5b3802fb5b16
expected_predecessor_0d7_note_sha256=66bec08941d7bd1b936bf94a8925b6ed9f7f3b53ae6e0684127fa3b82138c71a
expected_vllm_head=d154d90d6c4bcf26a0c78ac4f3e43621c14333ba
expected_vllm_tree=6310c33970329a4e4a9683ab7c94c1f4573a6cc8
expected_kernel_head=baaa05bb4e92901219a5a072dd63f2474896f6d1
expected_kernel_tree=e7e7d1063f232a383c98c1820cebb94c45b4906e
expected_base_digest=sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876
expected_control_image_id=sha256:51ceafc2ffed75e0a7f1166b6cd55251516502363a9d00d12fe0ad4b3469e70b
expected_both_image_id=sha256:358fb358a30463ededcb9ead252d0841b29eeeac684be756e16528329cb1030e
expected_host_kernel=7.0.0-30-generic
expected_host_boot_id=086de284-0771-4269-9cb2-e064fe303e40
diagnostic_floor=30.2178
strict_floor=30.31067504052998

die() {
  wrapper_failure_reason=$*
  printf 'error: %s\n' "$*" >&2
  exit 1
}

for command_name in awk chmod cmp cp date df docker env find findmnt flock git grep \
  jq mv pgrep realpath rg sed sha256sum sort ss sudo sync timeout tr uname unzip \
  wc xargs; do
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

verify_overlay_payload() {
  local root=$1 manifest_sha=$2 count=$3 metadata_sha=$4 readme_sha=$5
  local actual_count top_files unexpected_node
  [[ -d $root/source && ! -L $root && ! -L $root/source ]] ||
    die "protected overlay payload is incomplete or linked: $root"
  top_files=$(find "$root" -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort) ||
    die "protected overlay top-level scan failed: $root"
  [[ $top_files == $'README.md\nmanifest.sha256\nmetadata.json' ]] ||
    die "protected overlay top-level file set changed: $root"
  [[ $(sha256sum "$root/manifest.sha256" | awk '{print $1}') == "$manifest_sha" &&
     $(sha256sum "$root/metadata.json" | awk '{print $1}') == "$metadata_sha" &&
     $(sha256sum "$root/README.md" | awk '{print $1}') == "$readme_sha" ]] ||
    die "protected overlay metadata changed: $root"
  actual_count=$(find "$root/source" -type f | wc -l) ||
    die "protected overlay file-count scan failed: $root"
  [[ $actual_count -eq $count &&
     $(find "$root/source" -type f -name '*.best_config' | wc -l) -eq $count &&
     $(find "$root" -type f | wc -l) -eq $((count + 3)) ]] ||
    die "protected overlay regular-file set changed: $root"
  unexpected_node=$(find "$root" -mindepth 1 ! -type f ! -type d -print -quit) ||
    die "protected overlay node-type scan failed: $root"
  [[ -z $unexpected_node ]] ||
    die "protected overlay contains a symlink or special node: $unexpected_node"
  (
    cd "$root/source"
    sha256sum -c ../manifest.sha256 >/dev/null
  ) || die "protected overlay payload checksum failed: $root"
}

verify_protected_values() {
  local manifest_path=${1:-$protected_manifest}
  local tp2_path=${2:-$tp2_overlay}
  local tp4_path=${3:-$tp4_overlay}
  local actual_protected_values_sha
  [[ $(sha256sum "$manifest_path" | awk '{print $1}') == \
     "$expected_protected_manifest_sha256" ]] ||
    die 'whole protected overlay manifest changed'
  actual_protected_values_sha=$(
    jq -cS '.protected_target_only_decode_tok_s' "$manifest_path" |
      sha256sum | awk '{print $1}'
  )
  [[ $actual_protected_values_sha == "$expected_protected_values_sha256" ]] ||
    die 'complete protected performance ledger changed'
  jq -e '
    .protected_target_only_decode_tok_s.pinned_diagnostic.tp1 == [30.2178, 30.2569] and
    .protected_target_only_decode_tok_s.pinned_diagnostic.tp2 == [48.8301, 48.950458800865434] and
    .protected_target_only_decode_tok_s.pinned_diagnostic.tp4 == [71.6741, 71.5488] and
    .protected_target_only_decode_tok_s.pinned_strict.tp1 == [30.31067504052998] and
    .protected_target_only_decode_tok_s.pinned_strict.tp2 == [49.01965141150585] and
    .protected_target_only_decode_tok_s.pinned_strict.tp4 == [71.29326283364946, 71.39843006187554] and
    .protected_target_only_decode_tok_s.a356_stock_strict.tp4 == [71.9001988117144, 71.2457420049019] and
    .protected_target_only_decode_tok_s.a356_tp2_decision_overlay_diagnostic == [49.05894025767351] and
    .protected_target_only_decode_tok_s.a356_tp2_decision_overlay_strict == [49.00935245117815] and
    .protected_target_only_decode_tok_s.a356_tp4_decision_overlay_diagnostic == [71.72254506718171] and
    .protected_target_only_decode_tok_s.a356_tp4_decision_overlay_strict == [71.35287190161719, 71.45427094575045] and
    .protected_target_only_decode_tok_s["0ecc_qualified_stock_control"].strict == [30.324297716696414, 30.325970521145816]
  ' "$manifest_path" >/dev/null || die 'protected performance values changed'
  verify_overlay_payload "$tp2_path" "$expected_tp2_manifest_sha256" 78 \
    "$expected_tp2_metadata_sha256" "$expected_tp2_readme_sha256"
  verify_overlay_payload "$tp4_path" "$expected_tp4_manifest_sha256" 152 \
    "$expected_tp4_metadata_sha256" "$expected_tp4_readme_sha256"
}

verify_batch_invariant_build_assets() {
  local archive_dir=$1 archived_source_identity archived_source_canonical
  local wheel_members required_member required_count legacy_member legacy_count
  local image_spec image_id expected_lane image_inspect source_json import_json
  local installed_json image_source_canonical
  local -a archived_vllm_wheels

  [[ $(sha256sum "$archive_dir/SHA256SUMS" | awk '{print $1}') == \
     "$expected_archive_manifest_sha256" ]] ||
    die 'external archive checksum manifest changed'
  archived_source_identity=$archive_dir/source-identity.json
  [[ $(sha256sum "$archived_source_identity" | awk '{print $1}') == \
     "$expected_source_identity_sha256" ]] ||
    die 'archived source identity changed'
  jq -e \
    --arg vllm "$expected_vllm_head" --arg tree "$expected_vllm_tree" \
    --arg version "$expected_vllm_package_version" \
    --arg source_sha "$expected_vllm_source_archive_sha256" \
    --arg batch_path "$expected_batch_invariant_config_path" \
    --arg batch_sha "$expected_batch_invariant_config_sha256" \
    --arg rust_extension "$expected_rust_extension_sha256" \
    --arg rust_frontend "$expected_rust_frontend_sha256" '
    .overlay == "none" and .vllm.head == $vllm and .vllm.tree == $tree and
    .vllm.package_version == $version and .vllm.archive_sha256 == $source_sha and
    .preserved_upstream_optimization_assets.batch_invariant_config.path == $batch_path and
    .preserved_upstream_optimization_assets.batch_invariant_config.sha256 == $batch_sha and
    .reused_rust.extension_sha256 == $rust_extension and
    .reused_rust.frontend_sha256 == $rust_frontend
  ' "$archived_source_identity" >/dev/null ||
    die 'archived source identity contract changed'
  archived_source_canonical=$(jq -cS . "$archived_source_identity") ||
    die 'could not canonicalize archived source identity'

  mapfile -t archived_vllm_wheels < <(
    find "$archive_dir" -maxdepth 1 -type f -name 'vllm-*.whl' -print |
      LC_ALL=C sort
  )
  [[ ${#archived_vllm_wheels[@]} -eq 1 ]] ||
    die 'external archive must contain exactly one vLLM wheel'
  [[ $(sha256sum "${archived_vllm_wheels[0]}" | awk '{print $1}') == \
     "$expected_vllm_wheel_sha256" ]] || die 'archived vLLM wheel changed'
  wheel_members=$(unzip -Z1 "${archived_vllm_wheels[0]}") ||
    die 'could not inventory archived vLLM wheel'
  for required_member in \
      vllm/model_executor/determinism/__init__.py \
      vllm/model_executor/determinism/batch_invariant.py \
      "$expected_batch_invariant_config_path"; do
    required_count=$(awk -v target="$required_member" \
      '$0 == target {count++} END {print count + 0}' <<<"$wheel_members") ||
      die 'required wheel-member count failed'
    [[ $required_count -eq 1 ]] ||
      die "required batch-invariant wheel member changed: $required_member"
  done
  [[ $(unzip -p "${archived_vllm_wheels[0]}" \
        "$expected_batch_invariant_config_path" | sha256sum | awk '{print $1}') == \
     "$expected_batch_invariant_config_sha256" ]] ||
    die 'archived batch-invariant config bytes changed'
  for legacy_member in \
      vllm/model_executor/layers/batch_invariant.py \
      vllm/model_executor/layers/batch_invariant_configs.py; do
    legacy_count=$(awk -v target="$legacy_member" \
      '$0 == target {count++} END {print count + 0}' <<<"$wheel_members") ||
      die 'legacy wheel-member count failed'
    [[ $legacy_count -eq 0 ]] ||
      die "archived wheel retains a legacy batch-invariant member: $legacy_member"
  done

  for image_spec in \
      "$expected_control_image_id|current-vllm-stock-kernel" \
      "$expected_both_image_id|both-current-zero-overlay"; do
    IFS='|' read -r image_id expected_lane <<<"$image_spec"
    image_inspect=$(sudo -S -p '' docker image inspect "$image_id" \
      <"$sudo_pass_file") || die "exact image is absent: $image_id"
    jq -e \
      --arg image "$image_id" --arg lane "$expected_lane" \
      --arg vllm "$expected_vllm_head" \
      --arg batch_path "$expected_batch_invariant_config_path" \
      --arg batch_sha "$expected_batch_invariant_config_sha256" '
      .[0].Id == $image and .[0].Config.Labels["neural.download.build.lane"] == $lane and
      .[0].Config.Labels["neural.download.overlay"] == "none" and
      .[0].Config.Labels["neural.download.vllm.head"] == $vllm and
      .[0].Config.Labels["neural.download.vllm.batch_invariant_config.path"] == $batch_path and
      .[0].Config.Labels["neural.download.vllm.batch_invariant_config.sha256"] == $batch_sha and
      ([.[0].Config.Env[] | select(startswith("VLLM_BATCH_INVARIANT="))] | length) == 0
    ' <<<"$image_inspect" >/dev/null ||
      die "image optimization-asset label or disabled-state gate failed: $image_id"
    source_json=$(sudo -S -p '' docker run --rm --network=none \
      --entrypoint /bin/bash "$image_id" -lc \
      'cat /opt/neural-download/source-identity.json' <"$sudo_pass_file") ||
      die "could not read in-image source identity: $image_id"
    image_source_canonical=$(jq -cS . <<<"$source_json") ||
      die 'could not canonicalize in-image source identity'
    [[ $image_source_canonical == "$archived_source_canonical" ]] ||
      die "in-image and archived source identities differ: $image_id"
    import_json=$(sudo -S -p '' docker run --rm --network=none \
      --entrypoint /bin/bash "$image_id" -lc \
      'cat /opt/neural-download/import-receipt.json' <"$sudo_pass_file") ||
      die "could not read in-image import receipt: $image_id"
    jq -e \
      --arg lane "$expected_lane" --arg vllm "$expected_vllm_head" \
      --arg version "$expected_vllm_package_version" \
      --arg batch_path "$expected_batch_invariant_config_path" \
      --arg batch_sha "$expected_batch_invariant_config_sha256" '
      .build_lane == $lane and .vllm_head == $vllm and .vllm_version == $version and
      .batch_invariant_config_path == $batch_path and
      .batch_invariant_config_sha256 == $batch_sha
    ' <<<"$import_json" >/dev/null ||
      die "in-image import receipt lost the optimization asset: $image_id"
    installed_json=$(sudo -S -p '' docker run --rm --network=none \
      --entrypoint /opt/venv/bin/python "$image_id" -c '
import hashlib, importlib.util, json, pathlib, sys
relative = pathlib.PurePosixPath(sys.argv[1])
expected = sys.argv[2]
spec = importlib.util.find_spec("vllm")
if spec is None or not spec.submodule_search_locations or relative.parts[0] != "vllm":
    raise SystemExit("installed vLLM package is not discoverable")
root = pathlib.Path(next(iter(spec.submodule_search_locations))).resolve()
required = [
    root / "model_executor/determinism/__init__.py",
    root / "model_executor/determinism/batch_invariant.py",
    root.joinpath(*relative.parts[1:]),
]
if any(not item.is_file() or item.is_symlink() for item in required):
    raise SystemExit("installed batch-invariant member is missing or linked")
actual = hashlib.sha256(required[-1].read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit("installed batch-invariant config hash changed")
legacy = [
    root / "model_executor/layers/batch_invariant.py",
    root / "model_executor/layers/batch_invariant_configs.py",
]
if any(item.exists() or item.is_symlink() for item in legacy):
    raise SystemExit("installed package retains a legacy batch-invariant member")
print(json.dumps({"path": str(relative), "sha256": actual,
                  "required": len(required), "legacy_absent": len(legacy)}))
' "$expected_batch_invariant_config_path" \
      "$expected_batch_invariant_config_sha256" <"$sudo_pass_file") ||
      die "direct installed-package optimization-asset check failed: $image_id"
    jq -e --arg path "$expected_batch_invariant_config_path" \
      --arg sha "$expected_batch_invariant_config_sha256" '
      .path == $path and .sha256 == $sha and .required == 3 and .legacy_absent == 2
    ' <<<"$installed_json" >/dev/null ||
      die "direct installed-package optimization-asset receipt changed: $image_id"
  done
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
    .schema == "neural-download-qwen38-postreboot-hardware-gate-v3" and
    .passed == true and .gate_complete == true and .failure_stage == "complete" and
    .host.boot_id == $boot_id and .host.kernel == $kernel and
    .host.taint_pre == "0" and .host.taint_post == "0" and
    .repo_head == $repo_head and .gates.four_device_identity == true and
    .gates.per_card_compute == true and .gates.four_device_peer_read == true and
    .gates.four_rank_xccl_allreduce == true and .gates.repo_postflight == true and
    .gates.atomic_lock_handoff == true and
    .gates.torch_runtime_coherent == true and
    .gates.root_nvme_health == true and
    .gates.selector_and_mask_combined == false and
    .gates.kernel_reject_events == 0 and
    (.gates.known_corrected_root_nvme_events == 0 or
      .gates.known_corrected_root_nvme_events == 1)
  ' "$hardware_gate/summary.json" >/dev/null ||
    die 'post-reboot hardware gate is not valid for this commit and boot'
}

for required in "$runner" "$receipt" "$suite" "$baseline" \
  "$model_manifest" "$model_verifier" "$bench_helper" "$quality_helper" \
  "$kernel_delta_classifier" "$kernel_delta_classifier_test" "$prereg" \
  "$hardware_gate_runner" "$build_script" "$build_dockerfile" \
  "$protected_manifest" "$tp2_overlay" "$tp4_overlay" \
  "$predecessor_6a9_record" "$predecessor_6a9_note" \
  "$predecessor_342_record" "$predecessor_342_note" \
  "$predecessor_0d7_record" "$predecessor_0d7_note"; do
  [[ -e $required ]] || die "missing input: $required"
done
[[ -r $sudo_pass_file ]] || die 'sudo password file is unreadable'
[[ $(sha256sum "$suite" | awk '{print $1}') == "$expected_suite_sha256" ]] ||
  die 'validation suite hash changed'
[[ $(sha256sum "$baseline" | awk '{print $1}') == "$expected_baseline_sha256" ]] ||
  die 'quality baseline hash changed'
[[ $(sha256sum "$receipt" | awk '{print $1}') == "$expected_receipt_sha256" ]] ||
  die 'exact d154 build receipt changed'
[[ $(sha256sum "$prereg" | awk '{print $1}') == "$expected_prereg_sha256" ]] ||
  die 'd154 untreated preregistration hash changed'
[[ $(sha256sum "$runner" | awk '{print $1}') == "$expected_runner_sha256" ]] ||
  die 'successful benchmark runner changed'
[[ $(sha256sum "$model_manifest" | awk '{print $1}') == \
   "$expected_model_manifest_sha256" &&
   $(sha256sum "$model_verifier" | awk '{print $1}') == \
   "$expected_model_verifier_sha256" &&
   $(sha256sum "$bench_helper" | awk '{print $1}') == \
   "$expected_bench_helper_sha256" &&
   $(sha256sum "$quality_helper" | awk '{print $1}') == \
   "$expected_quality_helper_sha256" ]] ||
  die 'model or qualification helper changed'
[[ $(sha256sum "$build_script" | awk '{print $1}') == \
   "$expected_build_script_sha256" &&
   $(sha256sum "$build_dockerfile" | awk '{print $1}') == \
   "$expected_build_dockerfile_sha256" ]] ||
  die 'current-main build input changed'
[[ $(sha256sum "$kernel_delta_classifier" | awk '{print $1}') == \
   "$expected_kernel_delta_classifier_sha256" ]] ||
  die 'kernel-delta classifier changed'
[[ $(sha256sum "$kernel_delta_classifier_test" | awk '{print $1}') == \
   "$expected_kernel_delta_classifier_test_sha256" ]] ||
  die 'kernel-delta classifier test changed'
[[ $(sha256sum "$hardware_gate_runner" | awk '{print $1}') == \
   "$expected_hardware_gate_runner_sha256" ]] ||
  die 'corrected hardware-gate runner changed'
[[ $(sha256sum "$predecessor_6a9_record" | awk '{print $1}') == \
   "$expected_predecessor_6a9_record_sha256" &&
   $(sha256sum "$predecessor_6a9_note" | awk '{print $1}') == \
   "$expected_predecessor_6a9_note_sha256" &&
   $(sha256sum "$predecessor_342_record" | awk '{print $1}') == \
   "$expected_predecessor_342_record_sha256" &&
   $(sha256sum "$predecessor_342_note" | awk '{print $1}') == \
   "$expected_predecessor_342_note_sha256" &&
   $(sha256sum "$predecessor_0d7_record" | awk '{print $1}') == \
   "$expected_predecessor_0d7_record_sha256" &&
   $(sha256sum "$predecessor_0d7_note" | awk '{print $1}') == \
   "$expected_predecessor_0d7_note_sha256" ]] ||
  die 'historical predecessor evidence changed'
[[ -x $classifier_test_python ]] || die 'classifier-test Python is not executable'
if classifier_test_receipt=$(PATH="$(dirname -- "$classifier_test_python"):/usr/bin:/bin" \
    PYTHONDONTWRITEBYTECODE=1 "$classifier_test_python" \
    "$kernel_delta_classifier_test" 2>&1); then
  :
else
  die "kernel-delta classifier test failed: $classifier_test_receipt"
fi
jq -e \
  --arg vllm "$expected_vllm_head" --arg vllm_tree "$expected_vllm_tree" \
  --arg kernel "$expected_kernel_head" --arg kernel_tree "$expected_kernel_tree" \
  --arg base "$expected_base_digest" --arg control "$expected_control_image_id" \
  --arg both "$expected_both_image_id" \
  --arg package "$expected_vllm_package_version" \
  --arg wheel "$expected_vllm_wheel_sha256" \
  --arg source "$expected_vllm_source_archive_sha256" \
  --arg build_script "$expected_build_script_sha256" \
  --arg dockerfile "$expected_build_dockerfile_sha256" \
  --arg control_static "$expected_control_static_preflight_sha256" \
  --arg both_static "$expected_both_static_preflight_sha256" \
  --arg rust_extension "$expected_rust_extension_sha256" \
  --arg rust_frontend "$expected_rust_frontend_sha256" \
  --arg batch_path "$expected_batch_invariant_config_path" \
  --arg batch_sha "$expected_batch_invariant_config_sha256" '
  .schema == "neural-download-absolute-current-main-build-v1" and
  .state == "static-preflight-passed-for-built-images-gpu-qualification-pending" and
  .mode == "--build-all" and .overlay == "none" and
  .vllm.head == $vllm and .vllm.tree == $vllm_tree and
  .vllm.package_version == $package and .vllm.wheel_sha256 == $wheel and
  .vllm.source_archive_sha256 == $source and
  .kernel.head == $kernel and .kernel.tree == $kernel_tree and
  .base_digest == $base and
  .build_inputs.script_sha256 == $build_script and
  .build_inputs.dockerfile_sha256 == $dockerfile and
  .reused_rust.extension_sha256 == $rust_extension and
  .reused_rust.frontend_sha256 == $rust_frontend and
  .preserved_upstream_optimization_assets.batch_invariant_config.path == $batch_path and
  .preserved_upstream_optimization_assets.batch_invariant_config.sha256 == $batch_sha and
  .images.current_vllm_stock_kernel.built == true and
  .images.current_vllm_stock_kernel.image_id == $control and
  .images.current_vllm_stock_kernel.static_preflight_passed == true and
  .images.current_vllm_stock_kernel.static_preflight_sha256 == $control_static and
  .images.both_current_zero_overlay.built == true and
  .images.both_current_zero_overlay.image_id == $both and
  .images.both_current_zero_overlay.static_preflight_passed == true and
  .images.both_current_zero_overlay.static_preflight_sha256 == $both_static and
  .promotion.qualified == false
' "$receipt" >/dev/null || die 'exact d154 build receipt contract changed'
archive_dir=$(jq -r .external_archive "$receipt")
[[ -d $archive_dir ]] || die 'd154 external build archive is absent'
(
  cd "$archive_dir"
  sha256sum -c SHA256SUMS >/dev/null
) || die 'd154 external build archive checksum failure'
cmp -s "$receipt" "$archive_dir/build-receipt.json" ||
  die 'tracked and archived d154 receipts differ'
verify_protected_values
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
[[ ! -v VLLM_BATCH_INVARIANT ]] ||
  die 'VLLM_BATCH_INVARIANT must be absent for untreated qualification'
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
if running_container_ids=$(sudo -S -p '' docker ps -q <"$sudo_pass_file"); then
  :
else
  die 'Docker running-container scan failed before the hardware gate'
fi
[[ -z $running_container_ids ]] ||
  die 'a Docker container is already running before the hardware gate'
if model_processes=$(pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server'); then
  die 'a model server process is already running before the hardware gate'
else
  model_pgrep_rc=$?
fi
[[ $model_pgrep_rc -eq 1 ]] || die 'model-process scan failed'
for campaign_port in 19802 19803 19804; do
  if port_listeners=$(ss -ltnH "sport = :$campaign_port"); then
    :
  else
    die "port $campaign_port listener scan failed"
  fi
  [[ -z $port_listeners ]] || die "port $campaign_port is already in use"
done
[[ $result_root == /* && $hardware_gate == /* ]] ||
  die 'campaign and hardware-gate roots must be absolute'
canonical_result_root=$(realpath -m -- "$result_root")
canonical_hardware_gate=$(realpath -m -- "$hardware_gate")
[[ $canonical_result_root == "$result_root" &&
   $canonical_hardware_gate == "$hardware_gate" ]] ||
  die 'frozen campaign roots must already be canonical'
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
  die 'exact d154 stock-kernel image is absent'
[[ $(sudo -S -p '' docker image inspect "$expected_both_image_id" \
    --format '{{.Id}}' <"$sudo_pass_file") == "$expected_both_image_id" ]] ||
  die 'exact d154 both-current image is absent'
sudo -S -p '' docker image inspect "$expected_both_image_id" \
  <"$sudo_pass_file" |
  jq -e 'all((.[0].Config.Env // [])[];
    startswith("VLLM_BATCH_INVARIANT=") | not)' >/dev/null ||
  die 'measured image unexpectedly sets VLLM_BATCH_INVARIANT'

acquire_campaign_locks
failure_stage=locked-image-asset-preflight
verify_batch_invariant_build_assets "$archive_dir"
failure_stage=postreboot-hardware-gate
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
  cp --reflink=never -- "$build_script" "$inputs/build-current-main-images.sh"
  cp --reflink=never -- "$build_dockerfile" \
    "$inputs/Dockerfile.absolute-current-main"
  cp --reflink=never -- "$kernel_delta_classifier" \
    "$inputs/kernel-delta-classifier.py"
  cp --reflink=never -- "$kernel_delta_classifier_test" \
    "$inputs/kernel-delta-classifier-test.py"
  printf '%s\n' "$classifier_test_receipt" \
    >"$inputs/kernel-delta-classifier-test.receipt.txt"
  cp --reflink=never -- "$prereg" "$inputs/preregistration.md"
  cp --reflink=never -- "$predecessor_6a9_record" \
    "$inputs/predecessor-6a9-speed-only-miss.json"
  cp --reflink=never -- "$predecessor_6a9_note" \
    "$inputs/predecessor-6a9-speed-only-miss.md"
  cp --reflink=never -- "$predecessor_342_record" \
    "$inputs/predecessor-342-r2-stale.json"
  cp --reflink=never -- "$predecessor_342_note" \
    "$inputs/predecessor-342-r2-stale.md"
  cp --reflink=never -- "$predecessor_0d7_record" \
    "$inputs/predecessor-0d7-r1-stale.json"
  cp --reflink=never -- "$predecessor_0d7_note" \
    "$inputs/predecessor-0d7-r1-stale.md"
  cp --reflink=never -- "$protected_manifest" \
    "$inputs/protected-overlay-manifest.json"
  cp -R --reflink=never -- "$tp2_overlay" "$inputs/protected-tp2-overlay"
  cp -R --reflink=never -- "$tp4_overlay" "$inputs/protected-tp4-overlay"
  cp --reflink=never -- "$archive_dir/SHA256SUMS" \
    "$inputs/build-archive-SHA256SUMS"
  cp --reflink=never -- "$archive_dir/source-identity.json" \
    "$inputs/source-identity.json"
  cp --reflink=never -- \
    "$archive_dir/current-vllm-stock-kernel-static-preflight.txt" \
    "$inputs/current-vllm-stock-kernel-static-preflight.txt"
  cp --reflink=never -- \
    "$archive_dir/both-current-zero-overlay-static-preflight.txt" \
    "$inputs/both-current-zero-overlay-static-preflight.txt"
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
    "$inputs/verify-model-direct.py" "$inputs/kernel-delta-classifier.py"
  find "$inputs" -type d -exec chmod 0555 {} +
  verify_inputs
}

verify_inputs() {
  local executable_inputs writable_input writable_input_dir input_symlink
  local input_special
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
  input_symlink=$(find "$inputs" -type l -print -quit) ||
    die 'frozen input symlink scan failed'
  [[ -z $input_symlink ]] || die "frozen inputs contain a symlink: $input_symlink"
  input_special=$(find "$inputs" -mindepth 1 ! -type f ! -type d -print -quit) ||
    die 'frozen input node-type scan failed'
  [[ -z $input_special ]] ||
    die "frozen inputs contain a special node: $input_special"
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
  [[ $(sha256sum "$inputs/kernel-delta-classifier.py" | awk '{print $1}') == \
     "$expected_kernel_delta_classifier_sha256" ]] ||
    die 'frozen kernel-delta classifier is not exact'
  [[ $(sha256sum "$inputs/kernel-delta-classifier-test.py" | awk '{print $1}') == \
     "$expected_kernel_delta_classifier_test_sha256" ]] ||
    die 'frozen kernel-delta classifier test is not exact'
  [[ $(sha256sum "$inputs/strict-smoke.sh" | awk '{print $1}') == \
       "$expected_runner_sha256" &&
     $(sha256sum "$inputs/model-manifest.json" | awk '{print $1}') == \
       "$expected_model_manifest_sha256" &&
     $(sha256sum "$inputs/verify-model-direct.py" | awk '{print $1}') == \
       "$expected_model_verifier_sha256" &&
     $(sha256sum "$inputs/bench-openai-realistic-suite.py" | awk '{print $1}') == \
       "$expected_bench_helper_sha256" &&
     $(sha256sum "$inputs/qwen38-text-quality-suite.py" | awk '{print $1}') == \
       "$expected_quality_helper_sha256" &&
     $(sha256sum "$inputs/build-current-main-images.sh" | awk '{print $1}') == \
       "$expected_build_script_sha256" &&
     $(sha256sum "$inputs/Dockerfile.absolute-current-main" | awk '{print $1}') == \
       "$expected_build_dockerfile_sha256" ]] ||
    die 'frozen runtime or build helper changed'
  [[ $(sha256sum "$inputs/predecessor-6a9-speed-only-miss.json" | awk '{print $1}') == \
       "$expected_predecessor_6a9_record_sha256" &&
     $(sha256sum "$inputs/predecessor-6a9-speed-only-miss.md" | awk '{print $1}') == \
       "$expected_predecessor_6a9_note_sha256" &&
     $(sha256sum "$inputs/predecessor-342-r2-stale.json" | awk '{print $1}') == \
       "$expected_predecessor_342_record_sha256" &&
     $(sha256sum "$inputs/predecessor-342-r2-stale.md" | awk '{print $1}') == \
       "$expected_predecessor_342_note_sha256" &&
     $(sha256sum "$inputs/predecessor-0d7-r1-stale.json" | awk '{print $1}') == \
       "$expected_predecessor_0d7_record_sha256" &&
     $(sha256sum "$inputs/predecessor-0d7-r1-stale.md" | awk '{print $1}') == \
       "$expected_predecessor_0d7_note_sha256" ]] ||
    die 'frozen historical predecessor evidence changed'
  [[ $(sha256sum "$inputs/build-archive-SHA256SUMS" | awk '{print $1}') == \
       "$expected_archive_manifest_sha256" &&
     $(sha256sum "$inputs/source-identity.json" | awk '{print $1}') == \
       "$expected_source_identity_sha256" &&
     $(sha256sum "$inputs/current-vllm-stock-kernel-static-preflight.txt" |
       awk '{print $1}') == "$expected_control_static_preflight_sha256" &&
     $(sha256sum "$inputs/both-current-zero-overlay-static-preflight.txt" |
       awk '{print $1}') == "$expected_both_static_preflight_sha256" ]] ||
    die 'frozen static build evidence changed'
  verify_protected_values "$inputs/protected-overlay-manifest.json" \
    "$inputs/protected-tp2-overlay" "$inputs/protected-tp4-overlay"
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
     $'kernel-delta-classifier.py\nqualification-runner.sh\nstrict-smoke.sh\nverify-model-direct.py' ]] ||
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
  validate_hardware_gate
  verify_protected_values
  live_lab_status=$(git -C "$repo" status --porcelain=v1 --untracked-files=all) ||
    die 'lab repository status check failed between untreated arms'
  [[ -z $live_lab_status ]] ||
    die 'lab repository became dirty between untreated arms'
  [[ $(git -C "$repo" branch --show-current) == main ]] ||
    die 'lab repository left main between untreated arms'
  frozen_lab_head=$(<"$inputs/lab-head.txt")
  [[ $(git -C "$repo" rev-parse HEAD) == "$frozen_lab_head" ]] ||
    die 'lab commit changed between untreated arms'
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
    jq -cer '
      .summary.tok_s_1_100_intervals_after_ttft.median |
      if type == "number" then . else empty end
    ' \
      "$bench_json" 2>/dev/null || printf 'null\n'
  else
    printf 'null\n'
  fi
}

read_required_median() {
  local bench_json=$1
  jq -er '
    .summary.tok_s_1_100_intervals_after_ttft.median |
    if type == "number" and isfinite and (isnan | not) and . > 0 then .
    else error("benchmark median is not a positive finite JSON number")
    end
  ' "$bench_json"
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

record_live_lab_close_observation() {
  local destination=$result_root/live-lab-origin-main.close.json
  local tmp=$result_root/.live-lab-origin-main.close.json.tmp.$$
  local frozen_head query_output query_rc live_head resolution checked_utc
  if [[ -f $inputs/lab-head.txt ]]; then
    frozen_head=$(<"$inputs/lab-head.txt")
  else
    frozen_head=$(git -C "$repo" rev-parse HEAD) || return 1
  fi
  if [[ -f $destination ]]; then
    jq -e --arg frozen "$frozen_head" '
      .schema == "neural-download-live-lab-close-observation-v1" and
      .frozen_lab_head == $frozen and
      (.resolution == "matched" or .resolution == "different" or
       .resolution == "unresolved")
    ' "$destination" >/dev/null
    return
  fi
  if query_output=$(timeout --signal=TERM --kill-after=5s 30s \
      git -C "$repo" ls-remote --exit-code origin refs/heads/main 2>&1); then
    query_rc=0
  else
    query_rc=$?
  fi
  live_head=$(awk 'NR == 1 {print $1}' <<<"$query_output")
  if [[ $query_rc -eq 0 && $live_head =~ ^[0-9a-f]{40}$ ]]; then
    if [[ $live_head == "$frozen_head" ]]; then
      resolution=matched
    else
      resolution=different
    fi
  else
    live_head=
    resolution=unresolved
  fi
  checked_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  jq -n \
    --arg checked_utc "$checked_utc" --arg frozen_head "$frozen_head" \
    --arg live_head "$live_head" --arg resolution "$resolution" \
    --argjson query_exit_code "$query_rc" '
    {
      schema: "neural-download-live-lab-close-observation-v1",
      checked_utc: $checked_utc,
      frozen_lab_head: $frozen_head,
      live_origin_main: (if $live_head == "" then null else $live_head end),
      query_exit_code: $query_exit_code,
      resolution: $resolution,
      gating: false,
      note: "Close-time remote lab movement is evidence only; local commit and engine-source immutability remain hard gates."
    }
  ' >"$tmp" || return 1
  mv -f -- "$tmp" "$destination"
}

write_campaign_evidence() {
  local manifest_tmp="$result_root/.campaign-evidence.sha256.tmp.$$"
  local digest_tmp="$result_root/.campaign-evidence.sha256.digest.tmp.$$"
  local symlink_output special_output

  symlink_output=$(
    cd "$result_root"
    find . -path './control-cache' -prune -o -type l -print
  ) || return 1
  [[ -z $symlink_output ]] || {
    printf 'refusing to seal symlinked campaign evidence:\n%s\n' \
      "$symlink_output" >&2
    return 1
  }
  special_output=$(
    cd "$result_root"
    find . -mindepth 1 -path './control-cache' -prune -o \
      ! -type f ! -type d -print
  ) || return 1
  [[ -z $special_output ]] || {
    printf 'refusing to seal special-node campaign evidence:\n%s\n' \
      "$special_output" >&2
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
  record_live_lab_close_observation
  write_campaign_evidence
  sync -f "$result_root"
}

root_exit() {
  local rc=$? failure_rc failure_tmp reason_tmp root_state
  trap - EXIT
  trap '' INT TERM HUP
  if [[ $rc -ne 0 && -d $result_root ]]; then
    set +e
    failure_rc=$rc
    root_state="failed-incomplete mode=$mode rc=$rc"
    if ! record_live_lab_close_observation; then
      failure_rc=94
      root_state="failed-incomplete mode=$mode rc=$rc live-lab-close-record=failed"
    fi
    if ! write_root_status "$root_state"; then
      failure_rc=95
    fi
    reason_tmp="$result_root/.failure-reason.txt.tmp.$$"
    if ! printf 'stage=%s\nreason=%s\n' "$failure_stage" \
        "${wrapper_failure_reason:-unclassified wrapper or command failure}" \
        >"$reason_tmp" ||
        ! mv -f -- "$reason_tmp" "$result_root/failure-reason.txt"; then
      failure_rc=99
      root_state="failed-incomplete mode=$mode rc=$rc failure-reason-seal=failed"
      write_root_status "$root_state" || true
    fi
    failure_tmp="$result_root/.campaign-failure.json.tmp.$$"
    if ! jq -n \
      --arg state "$root_state" --arg mode "$mode" --argjson rc "$rc" \
      --arg failure_reason \
        "${wrapper_failure_reason:-unclassified wrapper or command failure}" \
      --arg failure_stage "$failure_stage" \
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
        failure_stage: $failure_stage,
        failure_reason: $failure_reason,
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
    -u KERNEL_DELTA_CLASSIFIER \
    -u EXTRA_VLLM_ARGS -u PROMPT_IDS -u ONEAPI_DEVICE_SELECTOR \
    -u ZE_AFFINITY_MASK -u SYCL_DEVICE_FILTER -u SYCL_DEVICE_ALLOWLIST \
    -u UR_DEVICE_SELECTORS -u XPU_GRAPH -u COMPILATION_CONFIG \
    -u PYTHONPATH -u PYTHONHOME -u LD_PRELOAD -u LD_LIBRARY_PATH \
    -u QUALITY_BASELINE_JSON -u QUALITY_REQUIRE_BASELINE \
    -u CACHE_POLICY -u EXPECTED_CACHE_MANIFEST_SHA256 \
    -u LAB_REMOTE_FRESHNESS_POLICY -u EXPECTED_LAB_HEAD \
    -u VLLM_BATCH_INVARIANT \
    -u BEST_CONFIG_SEED_DIR -u EXPECTED_BEST_CONFIG_SEED_COUNT \
    -u EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256 \
    -u BEST_CONFIG_TARGET_AOT_NAMESPACE \
    -u EXPECTED_CACHE_OUTER_NAMESPACE -u EXPECTED_CACHE_CODE_HASH \
    -u EXPECTED_CACHE_COMPILER_HASH -u EXPECTED_CACHE_CONFIG_HASH \
    -u EXPECTED_CACHE_ENV_SHA256 -u EXPECTED_COMPUTATION_GRAPH_SHA256S \
    "$@"
}

common_env=()

initialize_common_env() {
  common_env=(
    LAB_REPO_ROOT="$repo"
    LAB_REMOTE_FRESHNESS_POLICY=frozen-local
    EXPECTED_LAB_HEAD="$(<"$inputs/lab-head.txt")"
    CURRENT_MAIN_BUILD_RECEIPT="$inputs/build-receipt.json"
    CURRENT_MAIN_MODEL_MANIFEST="$inputs/model-manifest.json"
    CURRENT_MAIN_MODEL_VERIFIER="$inputs/verify-model-direct.py"
    CURRENT_MAIN_BENCH_HELPER="$inputs/bench-openai-realistic-suite.py"
    CURRENT_MAIN_QUALITY_HELPER="$inputs/qwen38-text-quality-suite.py"
    KERNEL_DELTA_CLASSIFIER="$inputs/kernel-delta-classifier.py"
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
}

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

freeze_control_cache_directories() {
  local directory_manifest_tmp="$control_fresh_out/.cache-directories.post.txt.tmp.$$"
  local directory_digest_tmp="$control_fresh_out/.cache-directories.post.sha256.tmp.$$"
  sudo -S -p '' bash -c '
    set -euo pipefail
    cd "$1"
    find . -type d -printf "%P\n" | LC_ALL=C sort
  ' bash "$control_cache" <"$sudo_pass_file" >"$directory_manifest_tmp" ||
    die 'could not freeze fresh cache directory set'
  mv -f -- "$directory_manifest_tmp" \
    "$control_fresh_out/cache-directories.post.txt"
  sha256sum "$control_fresh_out/cache-directories.post.txt" | awk '{print $1}' \
    >"$directory_digest_tmp"
  mv -f -- "$directory_digest_tmp" \
    "$control_fresh_out/cache-directories.post.sha256"
  frozen_control_cache_directory_manifest_sha256=$(
    <"$control_fresh_out/cache-directories.post.sha256"
  )
  [[ $frozen_control_cache_directory_manifest_sha256 =~ ^[0-9a-f]{64}$ ]] ||
    die 'could not freeze fresh cache directory-manifest digest'
}

validate_control_cache_tree() {
  local cache_real symlink_output special_output expected_file_count
  local actual_file_count actual_directory_manifest_sha256
  [[ -d $control_cache && ! -L $control_cache ]] ||
    die 'control cache root is not a real directory'
  cache_real=$(realpath -e -- "$control_cache")
  [[ $cache_real == "$control_cache" ]] ||
    die 'control cache root is not the frozen canonical path'
  [[ $(findmnt -n -o FSTYPE --target "$control_cache") == ext4 ]] ||
    die 'control cache is not on ext4'
  symlink_output=$(sudo -S -p '' find "$control_cache" -type l -print -quit \
    <"$sudo_pass_file") || die 'control cache symlink scan failed'
  [[ -z $symlink_output ]] ||
    die "control cache contains a symlink: $symlink_output"
  special_output=$(sudo -S -p '' find "$control_cache" \
    ! -type f ! -type d -print -quit <"$sudo_pass_file") ||
    die 'control cache node-type scan failed'
  [[ -z $special_output ]] ||
    die "control cache contains a special node: $special_output"
  expected_file_count=$(wc -l <"$control_fresh_out/cache-manifest.post.sha256")
  actual_file_count=$(sudo -S -p '' find "$control_cache" -type f \
    <"$sudo_pass_file" | wc -l)
  [[ $actual_file_count -eq $expected_file_count ]] ||
    die 'control cache regular-file count changed'
  [[ $frozen_control_cache_directory_manifest_sha256 =~ ^[0-9a-f]{64}$ &&
     $(sha256sum "$control_fresh_out/cache-directories.post.txt" |
       awk '{print $1}') == "$frozen_control_cache_directory_manifest_sha256" &&
     $(<"$control_fresh_out/cache-directories.post.sha256") == \
       "$frozen_control_cache_directory_manifest_sha256" ]] ||
    die 'frozen control cache directory manifest changed'
  actual_directory_manifest_sha256=$(
    sudo -S -p '' bash -c '
      set -euo pipefail
      cd "$1"
      find . -type d -printf "%P\n" | LC_ALL=C sort
    ' bash "$control_cache" <"$sudo_pass_file" |
      sha256sum | awk '{print $1}'
  )
  [[ $actual_directory_manifest_sha256 == \
     "$frozen_control_cache_directory_manifest_sha256" ]] ||
    die 'control cache directory set changed'
  sudo -S -p '' bash -c '
    set -euo pipefail
    cd "$1"
    sha256sum -c "$2" >/dev/null
  ' bash "$control_cache" "$control_fresh_out/cache-manifest.post.sha256" \
    <"$sudo_pass_file" || die 'actual control cache bytes changed'
}

run_control_fresh() {
  failure_stage=freeze-inputs
  prepare_inputs
  initialize_common_env
  verify_inputs
  failure_stage=control-fresh-diagnostic
  run_strict_arm control-fresh "$control_fresh_out" \
    run_clean_env "${common_env[@]}" \
    CACHE_POLICY=fresh NATURAL_EOS=0 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19802 \
      "$control_fresh_out" "$inputs/validation-suite.json" "$control_cache"
  frozen_control_cache_manifest_sha256=$(
    <"$control_fresh_out/cache-manifest.post.sha256.digest"
  )
  [[ $frozen_control_cache_manifest_sha256 =~ ^[0-9a-f]{64}$ ]] ||
    die 'fresh arm did not produce a valid cache-manifest digest'
  [[ $(sha256sum "$control_fresh_out/cache-manifest.post.sha256" |
      awk '{print $1}') == "$frozen_control_cache_manifest_sha256" ]] ||
    die 'fresh cache manifest does not match its frozen digest'
  freeze_control_cache_directories
  validate_control_cache_tree
  actual=$(read_required_median "$control_fresh_out/bench.json") ||
    die 'fresh diagnostic benchmark median is invalid'
  write_speed_gate "$control_fresh_out/current-base-speed-gate.status" \
    "$actual" "$diagnostic_floor"
  verify_inputs
  write_root_status 'control-fresh-complete-awaiting-replay-a'
}

require_control_fresh() {
  verify_inputs
  validate_control_cache_tree
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
  failure_stage=control-replay-a-preflight
  require_control_fresh
  failure_stage=control-strict-quality-replay-a
  run_strict_arm control-replay-a "$control_replay_a_out" \
    run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay \
    EXPECTED_CACHE_MANIFEST_SHA256="$frozen_control_cache_manifest_sha256" \
    NATURAL_EOS=1 QUALITY=1 QUALITY_REQUIRE_BASELINE=1 \
    QUALITY_BASELINE_JSON="$inputs/quality-baseline.json" \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19803 \
      "$control_replay_a_out" "$inputs/validation-suite.json" "$control_cache"
  actual=$(read_required_median "$control_replay_a_out/bench.json") ||
    die 'strict replay A benchmark median is invalid'
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
  failure_stage=control-replay-b-preflight
  require_control_replay_a
  failure_stage=control-strict-replay-b
  run_strict_arm control-replay-b "$control_replay_b_out" \
    run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay \
    EXPECTED_CACHE_MANIFEST_SHA256="$frozen_control_cache_manifest_sha256" \
    NATURAL_EOS=1 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19804 \
      "$control_replay_b_out" "$inputs/validation-suite.json" "$control_cache"
  [[ $(<"$control_replay_b_out/final.status") == pass ]] ||
    die 'untreated control replay B did not pass its non-speed gates'
  actual_b=$(read_required_median "$control_replay_b_out/bench.json") ||
    die 'strict replay B benchmark median is invalid'
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
  failure_stage=aggregate-control-result
  record_live_lab_close_observation

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
    --arg cache_directory_manifest_sha256 \
      "$frozen_control_cache_directory_manifest_sha256" \
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
    --slurpfile q "$control_replay_a_out/quality.json" \
    --slurpfile lab_close "$result_root/live-lab-origin-main.close.json" '
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
    (([$d[0], $a[0], $b[0]] | all(.[];
      .realistic_final_gate.passed == true and
      .summary.tok_s_1_100_intervals_after_ttft.count == 25 and
      (.summary.tok_s_1_100_intervals_after_ttft.median |
        type == "number" and isfinite and (isnan | not) and . > 0) and
      .fresh_response_validity.valid == true and
      .fresh_response_validity.prompt_count == 25 and
      .fresh_response_validity.cached_tokens_all_zero == true and
      (.fresh_response_validity.cached_tokens | length) == 25 and
      all(.fresh_response_validity.cached_tokens[]; . == 0) and
      (.rows | length) == 25 and all(.rows[]; .cached_tokens == 0)))) as $bench_ok |
    (($q[0].pass_all == true and $q[0].baseline_match_all == true and
      ($q[0].exact_cases | length) == 7 and
      all($q[0].exact_cases[];
        .pass == true and .usage.prompt_tokens_details.cached_tokens == 0) and
      ($q[0].repeat_case.runs | length) == 8 and
      $q[0].repeat_case.pass == true and
      ($q[0].repeat_case.unique_hashes | length) == 1 and
      all($q[0].repeat_case.runs[];
        .usage.prompt_tokens_details.cached_tokens == 0) and
      $q[0].long_context_case.pass == true and
      $q[0].long_context_case.requested_context_tokens == 8192 and
      $q[0].long_context_case.actual_prompt_tokens == 7617 and
      $q[0].long_context_case.usage.prompt_tokens_details.cached_tokens == 0 and
      ($q[0].baseline_comparisons | length) == 24 and
      all($q[0].baseline_comparisons[]; . == true))) as $quality_ok |
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
      live_lab_close_observation: $lab_close[0],
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
        compiled_cache_directory_manifest_sha256: $cache_directory_manifest_sha256,
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
    --arg cache_directory_manifest \
      "$frozen_control_cache_directory_manifest_sha256" \
    --argjson diagnostic_floor "$diagnostic_floor" \
    --argjson strict_floor "$strict_floor" '
    .schema == "neural-download-current-main-tp1-untreated-control-result-v1" and
    .state == "complete" and .run_root == $run_root and
    .identity.vllm_head == $vllm and .identity.vllm_tree == $vllm_tree and
    .identity.kernel_head == $kernel and .identity.kernel_tree == $kernel_tree and
    .identity.base_digest == $base and .identity.image_id == $image and
    .identity.receipt_sha256 == $receipt and .identity.lab_head == $lab_head and
    .host.kernel == $host_kernel and .host.boot_id == $boot_id and
    .live_lab_close_observation.schema ==
      "neural-download-live-lab-close-observation-v1" and
    .live_lab_close_observation.frozen_lab_head == $lab_head and
    .live_lab_close_observation.gating == false and
    (.live_lab_close_observation.resolution == "matched" or
     .live_lab_close_observation.resolution == "different" or
     .live_lab_close_observation.resolution == "unresolved") and
    .floors_tok_s.diagnostic == $diagnostic_floor and
    .floors_tok_s.strict == $strict_floor and
    (.qualification_ready | type) == "boolean" and
    (.evidence.all_non_speed_gates_pass | type) == "boolean" and
    .evidence.postreboot_hardware_gate_pass == true and
    .evidence.frozen_inputs_manifest_sha256 == $inputs_manifest and
    .evidence.compiled_cache_manifest_sha256 == $cache_manifest and
    .evidence.compiled_cache_directory_manifest_sha256 == $cache_directory_manifest
  ' "$result_root/control-result.json" >/dev/null ||
    die 'untreated aggregate result failed terminal identity validation'
}

run_control_fresh
run_control_replay_a
run_control_replay_b
failure_stage=terminal-result-verification
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
failure_stage=terminal-seal
seal_campaign_status "$terminal_state"
trap - EXIT
exit "$terminal_rc"
