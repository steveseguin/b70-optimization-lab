#!/usr/bin/env bash
set -Eeuo pipefail

# Report-only recovery for the 6a9c build whose two immutable images and
# static preflights completed before ENOSPC stopped the normal receipt writer.
# This script never builds, retags, removes, or launches with a GPU.

umask 077

mode=${1:-}
[[ $# -eq 1 && $mode == --recover ]] || {
  printf 'usage: %s --recover\n' "$0" >&2
  exit 2
}

repo=/home/steve/llm-optimizations
lane=$repo/experiments/qwen38-27b-b70
build_script=$lane/scripts/build-20260823-qwen38-absolute-current-main-images.sh
dockerfile=$lane/docker/Dockerfile.absolute-current-main
script_path=$(realpath -e -- "${BASH_SOURCE[0]}")
build_root=/home/steve/builds/qwen38-current-main-20260824T185928Z-6a9c69fa85-baaa05bb4e
archive_dir=/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T185928Z-6a9c69fa85-baaa05bb4e
archive_stage=${archive_dir}.recovery-partial
vllm_source=/home/steve/src/vllm-current-main
kernel_source=/home/steve/src/vllm-xpu-kernels-current-main
kernel_artifact_dir=/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/upstream-kernel-baaa05bb-artifact-9508328924
sudo_password_file=${SUDO_PASSWORD_FILE:-/home/steve/SUDOPASSWORD.txt}

source_identity=$build_root/context/source-identity.json
source_archive=$build_root/vllm-source.tar
wheel=$build_root/vllm-wheel/vllm-0.26.1rc1.dev1157+g6a9c69fa8.xpu-cp312-cp312-linux_x86_64.whl
receipt_dir=$build_root/receipts
log_dir=$build_root/logs
build_receipt=$receipt_dir/build-receipt.json
failure_snapshot=$receipt_dir/build-failure-snapshot.json
protected_manifest=$lane/data/2026-08-23-qwen38-current-main-overlay-manifest.json
tp2_overlay=$lane/autotune-winner-overlays/tp2-e9d1398-best-config
tp4_overlay=$lane/autotune-winner-overlays/tp4-e9d1398-best-config
attempt_record=$lane/data/2026-08-24-qwen38-6a9c69fa85-enospc-build-attempt.json
prereg=$lane/notes/2026-08-24-qwen38-6a9c69fa85-enospc-receipt-recovery-prereg.md

vllm_head=6a9c69fa851389dcf1ee5d3a2363e27af665d26d
vllm_tree=baf2301fb3f993537b07b6132b4d980efca2e7e4
vllm_version=0.26.1rc1.dev1157+g6a9c69fa8.xpu
kernel_head=baaa05bb4e92901219a5a072dd63f2474896f6d1
kernel_tree=e7e7d1063f232a383c98c1820cebb94c45b4906e
kernel_version=0.1.dev1+gbaaa05bb4
base_digest=sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876
base_tag=vllm/vllm-openai-xpu:nightly
build_utc=2026-08-24T18:59:28Z
build_lab_head=feffa703cf33ed86025d4833d1e4aa2a52243471
build_lab_tree=d65181c5865e4941bb7ab3163bf97d3e05af4a61

control_tag=neural-download/vllm-openai-xpu:vllm-6a9c69fa85-kernel-stock-3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876
both_tag=neural-download/vllm-openai-xpu:vllm-6a9c69fa85-kernel-baaa05bb4e-official
control_id=sha256:24ca5f6b6e5a14f71f43f82469f6e9debd36b2965942932e1646f377e30799cf
both_id=sha256:f86c4c78d76a484f5d54eda310419c91a2471634ab97782022ef7573fc19a7d9

build_script_sha=fc780ca35a9ea8b3022825ae9cebbc1e2e84c42a40a62289649bc67cd96eec16
dockerfile_sha=d9866acd99e7de78f675af1bc2aba49d4c5c749e0c79ea22d1f45d2ce745a749
source_identity_sha=7d2fe9b64a40cc868c7a5f6ac6d8c612888bd6e271a9c227aad19c3c4f27fac5
source_archive_sha=5eb2277adbf0ea46ec43ddc3a2f10c11aca26de45955f2df60d27c414d5dc2ce
wheel_sha=49832725de5066a25429a6f78ae2b448b9ff2e51af9ad34a7de89013e5b089db
rust_extension_sha=7cb3df775d2183d2c1a7d3025a8f49b9a79548d157993969fc0c49f46c725c52
rust_frontend_sha=a415187153b2a8b10683494c7b22472158b487c69023713313542d4bc09c4c92

control_inspect_sha=b67b98503acd75cdcdeb6165982c3058e90180d36dd0e005d9ab5fe43a126bcd
both_inspect_sha=e06ef362ed31ceae4a9b8a14c436c2e1c1feb5b0ffc5cffcb2b4430177333ce0
control_preflight_sha=7c201fffaa55300c0a44920a2c346a66c190dcf27acdba8016a888ffbe993003
both_preflight_sha=b6e4b3789ec0b4d41d2d2be53d48b86e9bf514d681d8af25d61a0c1a247a99e8
control_tag_sha=0ad11104c8eef8e107a9861b5ca310883c64c5a46827f56a9b8375fbe0125b51
empty_sha=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
both_tag_recovered_sha=796109d0402f0d174f1f07efcd9eaf9b2256d592b30aeb4fe827ff268a02c8c5
tp2_manifest_sha=65c574c24d24804d250e5179e9a202ec9e77e8c5740cea121b7660d8ee854757
tp4_manifest_sha=a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2
protected_values_sha=e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f

wheel_log_sha=77e834ef34033d4498db5fbcbcdf7d86bec3aa78eb114ec505224b111b378fb2
control_log_sha=a13d784d3e90b94c240e5a5c9911f17e815bf0ce230156d57fb49c0dd2272327
both_log_sha=f72ab213b9846038e786aca91f24c1ef99afd638ad21b17b920f0000bc28f87e

kernel_run_id=32692290527
kernel_artifact_id=9508328924
kernel_artifact_name=vllm-xpu-kernels--20260824-050903
kernel_artifact_digest=sha256:ce94da86eb14e61673a10db5c8a2c3fffb49a5f61ec9d36c210601062f887f10
kernel_artifact_size=475965714
kernel_wheel_sha=7b886fa814469aef8904118729f31f2fe77559f3c5219bd0ecf799a904387483
kernel_build_info_sha=640dc7b2abee85037aa99eac4955e5092ccebd4479c07d0cafd0ea174e13dc15
kernel_workflow_sha=7670fc876c4f4c9deab5f972f65324c6a75ad61eb1dadea4759ae41282a78c12
chunk_sha=6091d2b7cda8340333beb26d6dde09c45689c1fd19e5a9e77352d8dedb7cbc59
paged_sha=2c46aea68f7d70a0e40acd3de15a4afefe5c9f2ff0f105592d8a7d0c828bcebc
minimum_root_free_kib=12582912

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

for command_name in awk cmp cp date df docker find findmnt flock gh git grep \
  jq mkdir mktemp mv pgrep realpath rg rmdir sha256sum sort stat sudo sync \
  timeout unzip wc xargs; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done
[[ -r $sudo_password_file ]] || die 'sudo password file is not readable'

docker_cmd() {
  timeout --signal=TERM --kill-after=5s 60s \
    sudo -S -p '' docker "$@" <"$sudo_password_file"
}

gh_api() {
  timeout --signal=TERM --kill-after=5s 60s gh api "$@"
}

verify_sha() {
  local path=$1 expected=$2 actual
  [[ -f $path ]] || die "missing file: $path"
  actual=$(sha256sum "$path" | awk '{print $1}')
  [[ $actual == "$expected" ]] || die "hash mismatch: $path"
}

live_head() {
  timeout --signal=TERM --kill-after=5s 30s \
    git ls-remote --exit-code "$1" refs/heads/main |
    awk 'NR == 1 {print $1}'
}

verify_inspect() {
  local path=$1 image_id=$2 image_tag=$3 lane_name=$4 kernel_label=$5
  local kernel_tree_label=$6 kernel_wheel_label=$7 kernel_chunk_label=$8
  local kernel_paged_label=$9
  jq -e \
    --arg image_id "$image_id" --arg image_tag "$image_tag" \
    --arg lane_name "$lane_name" --arg kernel_label "$kernel_label" \
    --arg kernel_tree_label "$kernel_tree_label" \
    --arg kernel_wheel_label "$kernel_wheel_label" \
    --arg kernel_chunk_label "$kernel_chunk_label" \
    --arg kernel_paged_label "$kernel_paged_label" \
    --arg base_digest "$base_digest" --arg build_script_sha "$build_script_sha" \
    --arg dockerfile_sha "$dockerfile_sha" --arg vllm_head "$vllm_head" \
    --arg vllm_tree "$vllm_tree" --arg wheel_sha "$wheel_sha" \
    --arg source_archive_sha "$source_archive_sha" \
    --arg build_lab_head "$build_lab_head" --arg build_lab_tree "$build_lab_tree" \
    --arg rust_extension_sha "$rust_extension_sha" \
    --arg rust_frontend_sha "$rust_frontend_sha" --arg build_utc "$build_utc" '
      .[0] as $i |
      $i.Id == $image_id and
      (($i.RepoTags | index($image_tag)) != null) and
      $i.Config.Entrypoint == ["vllm", "serve"] and
      $i.Config.Cmd == null and
      ([ $i.Config.Env[] |
        select(test("^(ONEAPI_DEVICE_SELECTOR|ZE_AFFINITY_MASK|SYCL_DEVICE_FILTER|SYCL_DEVICE_ALLOWLIST|UR_DEVICE_SELECTORS)="))
      ] | length) == 0 and
      ($i.Config.Labels | length) == 21 and
      $i.Config.Labels["neural.download.overlay"] == "none" and
      $i.Config.Labels["neural.download.build.lane"] == $lane_name and
      $i.Config.Labels["neural.download.base.digest"] == $base_digest and
      $i.Config.Labels["neural.download.build.script.sha256"] == $build_script_sha and
      $i.Config.Labels["neural.download.build.dockerfile.sha256"] == $dockerfile_sha and
      $i.Config.Labels["neural.download.vllm.head"] == $vllm_head and
      $i.Config.Labels["neural.download.vllm.tree"] == $vllm_tree and
      $i.Config.Labels["neural.download.vllm.wheel.sha256"] == $wheel_sha and
      $i.Config.Labels["neural.download.vllm.archive.sha256"] == $source_archive_sha and
      $i.Config.Labels["neural.download.lab.head"] == $build_lab_head and
      $i.Config.Labels["neural.download.lab.tree"] == $build_lab_tree and
      $i.Config.Labels["neural.download.rust.extension.sha256"] == $rust_extension_sha and
      $i.Config.Labels["neural.download.rust.frontend.sha256"] == $rust_frontend_sha and
      $i.Config.Labels["neural.download.kernel.head"] == $kernel_label and
      $i.Config.Labels["neural.download.kernel.tree"] == $kernel_tree_label and
      $i.Config.Labels["neural.download.kernel.wheel.sha256"] == $kernel_wheel_label and
      $i.Config.Labels["neural.download.kernel.chunk_config.sha256"] == $kernel_chunk_label and
      $i.Config.Labels["neural.download.kernel.paged_config.sha256"] == $kernel_paged_label and
      $i.Config.Labels["org.opencontainers.image.created"] == $build_utc and
      $i.Config.Labels["org.opencontainers.image.revision"] == $vllm_head and
      $i.Config.Labels["org.opencontainers.image.version"] == "24.04"
    ' "$path" >/dev/null || die "image label mismatch: $image_tag"
}

verify_tag_binding() {
  local image_tag=$1 expected_id=$2 actual_id
  if actual_id=$(docker_cmd image inspect "$image_tag" --format '{{.Id}}'); then
    :
  else
    die "image tag inspection failed: $image_tag"
  fi
  [[ $actual_id == "$expected_id" ]] || die "image tag moved: $image_tag"
}

verify_overlay() {
  local overlay=$1 expected_manifest_sha=$2 expected_count=$3 count overlay_symlink
  [[ -d $overlay/source ]] || die "overlay source is absent: $overlay"
  verify_sha "$overlay/manifest.sha256" "$expected_manifest_sha"
  count=$(wc -l <"$overlay/manifest.sha256")
  [[ $count == "$expected_count" ]] || die "overlay manifest count differs: $overlay"
  count=$(find "$overlay/source" -type f | wc -l)
  [[ $count == "$expected_count" ]] || die "overlay payload count differs: $overlay"
  if overlay_symlink=$(find "$overlay/source" -type l -print -quit); then
    :
  else
    die "overlay symlink scan failed: $overlay"
  fi
  [[ -z $overlay_symlink ]] || die "overlay contains a symlink: $overlay"
  (
    cd "$overlay/source"
    sha256sum -c ../manifest.sha256 >/dev/null
  ) || die "overlay payload hash differs: $overlay"
}

verify_protected_values() {
  local actual_protected_values_sha
  actual_protected_values_sha=$(
    jq -cS '.protected_target_only_decode_tok_s' "$protected_manifest" |
      sha256sum | awk '{print $1}'
  )
  [[ $actual_protected_values_sha == "$protected_values_sha" ]] ||
    die 'complete protected performance ledger changed'
  jq -e '
    .protected_target_only_decode_tok_s.pinned_diagnostic.tp1 == [30.2178, 30.2569] and
    .protected_target_only_decode_tok_s.pinned_diagnostic.tp2 == [48.8301, 48.950458800865434] and
    .protected_target_only_decode_tok_s.pinned_diagnostic.tp4 == [71.6741, 71.5488] and
    .protected_target_only_decode_tok_s.pinned_strict.tp1 == [30.31067504052998] and
    .protected_target_only_decode_tok_s.pinned_strict.tp2 == [49.01965141150585] and
    .protected_target_only_decode_tok_s.pinned_strict.tp4 == [71.29326283364946, 71.39843006187554] and
    .protected_target_only_decode_tok_s.a356_tp2_decision_overlay_diagnostic == [49.05894025767351] and
    .protected_target_only_decode_tok_s.a356_tp2_decision_overlay_strict == [49.00935245117815] and
    .protected_target_only_decode_tok_s.a356_tp4_decision_overlay_diagnostic == [71.72254506718171] and
    .protected_target_only_decode_tok_s.a356_tp4_decision_overlay_strict == [71.35287190161719, 71.45427094575045]
  ' "$protected_manifest" >/dev/null || die 'protected performance ledger changed'
  verify_overlay "$tp2_overlay" "$tp2_manifest_sha" 78
  verify_overlay "$tp4_overlay" "$tp4_manifest_sha" 152
}

verify_official_kernel_artifact() {
  local run_result artifact_result
  if run_result=$(gh_api \
      "repos/vllm-project/vllm-xpu-kernels/actions/runs/$kernel_run_id"); then
    :
  else
    die 'official kernel workflow-run query failed'
  fi
  jq -e \
    --arg head "$kernel_head" --argjson run_id "$kernel_run_id" '
      .id == $run_id and .head_sha == $head and .head_branch == "main" and
      .status == "completed" and .conclusion == "success"
    ' <<<"$run_result" >/dev/null || die 'official kernel workflow run changed'

  if artifact_result=$(gh_api \
      "repos/vllm-project/vllm-xpu-kernels/actions/artifacts/$kernel_artifact_id"); then
    :
  else
    die 'official kernel artifact query failed'
  fi
  jq -e \
    --arg head "$kernel_head" --arg name "$kernel_artifact_name" \
    --arg digest "$kernel_artifact_digest" \
    --argjson run_id "$kernel_run_id" \
    --argjson artifact_id "$kernel_artifact_id" \
    --argjson size "$kernel_artifact_size" '
      .id == $artifact_id and .name == $name and .expired == false and
      .digest == $digest and .size_in_bytes == $size and
      .workflow_run.id == $run_id and .workflow_run.head_sha == $head and
      .workflow_run.head_branch == "main"
    ' <<<"$artifact_result" >/dev/null || die 'official kernel artifact metadata changed'

  grep -Fx "Commit: $kernel_head" "$kernel_artifact_dir/build_info.txt" >/dev/null ||
    die 'kernel build_info commit changed'
  grep -Fx 'Branch: main' "$kernel_artifact_dir/build_info.txt" >/dev/null ||
    die 'kernel build_info branch changed'
  grep -Fx 'Build Date: 20260824-050903' "$kernel_artifact_dir/build_info.txt" >/dev/null ||
    die 'kernel build_info date changed'
  grep -Fx 'Build Number: 421' "$kernel_artifact_dir/build_info.txt" >/dev/null ||
    die 'kernel build_info number changed'
  grep -Fx 'Workflow: wheel-per-commit' "$kernel_artifact_dir/build_info.txt" >/dev/null ||
    die 'kernel build_info workflow changed'
}

verify_frozen_evidence() {
  verify_sha "$build_script" "$build_script_sha"
  verify_sha "$dockerfile" "$dockerfile_sha"
  verify_sha "$source_identity" "$source_identity_sha"
  verify_sha "$source_archive" "$source_archive_sha"
  verify_sha "$wheel" "$wheel_sha"
  verify_sha "$log_dir/vllm-wheel-build.log" "$wheel_log_sha"
  verify_sha "$log_dir/current-vllm-stock-kernel-image-build.log" "$control_log_sha"
  verify_sha "$log_dir/both-current-zero-overlay-image-build.log" "$both_log_sha"
  verify_sha "$receipt_dir/current-vllm-stock-kernel-image-inspect.json" "$control_inspect_sha"
  verify_sha "$receipt_dir/both-current-zero-overlay-image-inspect.json" "$both_inspect_sha"
  verify_sha "$receipt_dir/current-vllm-stock-kernel-static-preflight.txt" "$control_preflight_sha"
  verify_sha "$receipt_dir/both-current-zero-overlay-static-preflight.txt" "$both_preflight_sha"
  verify_sha "$receipt_dir/current-vllm-stock-kernel-image-tag.txt" "$control_tag_sha"
  verify_sha "$receipt_dir/both-current-zero-overlay-image-tag.txt" "$empty_sha"
  verify_sha "${kernel_wheels[0]}" "$kernel_wheel_sha"
  verify_sha "$kernel_artifact_dir/build_info.txt" "$kernel_build_info_sha"
  verify_sha "$kernel_source/.github/workflows/wheel-per-commit.yaml" "$kernel_workflow_sha"
  verify_sha "$kernel_source/csrc/xpu/attn/kernel_configs/chunk_prefill_full.conf" "$chunk_sha"
  verify_sha "$kernel_source/csrc/xpu/attn/kernel_configs/paged_decode_full.conf" "$paged_sha"
  verify_protected_values
}

verify_quiescent_docker() {
  local running_container_ids active_builds active_build_rc
  if running_container_ids=$(docker_cmd ps -q); then
    :
  else
    die 'Docker container scan failed'
  fi
  [[ -z $running_container_ids ]] || die 'a container is running'
  if active_builds=$(pgrep -af \
      '[d]ocker (build|buildx build)|[b]uild-20260823-qwen38-absolute-current-main-images.sh --build'); then
    die "an image build is active: $active_builds"
  else
    active_build_rc=$?
  fi
  [[ $active_build_rc -eq 1 ]] || die 'active image-build process scan failed'
}

verify_packet_binding() {
  local actual_script_sha
  actual_script_sha=$(sha256sum "$script_path" | awk '{print $1}')
  [[ $actual_script_sha == "$recovery_script_sha" ]] ||
    die 'recovery script changed during recovery'
  jq -e --arg script "$script_path" --arg sha "$recovery_script_sha" '
    .recovery_packet.script == ($script | sub("^/home/steve/llm-optimizations/"; "")) and
    .recovery_packet.script_sha256 == $sha and
    .recovery_packet.status == "preregistered-not-run"
  ' "$attempt_record" >/dev/null || die 'attempt record does not bind this recovery script'
  rg -F "\`$recovery_script_sha\`" "$prereg" >/dev/null ||
    die 'preregistration does not bind this recovery script'
}

exec {recovery_lock_fd}>/tmp/qwen38-current-main-build-recovery.lock
flock -n "$recovery_lock_fd" || die 'another build recovery holds the lock'

[[ $(git -C "$repo" branch --show-current) == main ]] || die 'lab repo is not on main'
if lab_status=$(git -C "$repo" status --porcelain=v1 --untracked-files=all); then
  :
else
  die 'lab repo status check failed'
fi
[[ -z $lab_status ]] || die 'lab repo is not clean'
recovery_lab_head=$(git -C "$repo" rev-parse HEAD)
recovery_lab_tree=$(git -C "$repo" rev-parse 'HEAD^{tree}')
[[ $(git -C "$repo" rev-parse origin/main) == "$recovery_lab_head" ]] || die 'local lab origin/main differs'
[[ $(live_head git@github.com:steveseguin/b70-optimization-lab.git) == "$recovery_lab_head" ]] || die 'live lab origin/main differs'

[[ $(git -C "$vllm_source" branch --show-current) == main ]] || die 'vLLM source is not on main'
if vllm_status=$(git -C "$vllm_source" status --porcelain=v1 --untracked-files=all); then
  :
else
  die 'vLLM source status check failed'
fi
[[ -z $vllm_status ]] || die 'vLLM source is dirty'
[[ $(git -C "$vllm_source" rev-parse HEAD) == "$vllm_head" ]] || die 'vLLM source head differs'
[[ $(git -C "$vllm_source" rev-parse 'HEAD^{tree}') == "$vllm_tree" ]] || die 'vLLM source tree differs'
[[ $(git -C "$kernel_source" branch --show-current) == main ]] || die 'kernel source is not on main'
if kernel_status=$(git -C "$kernel_source" status --porcelain=v1 --untracked-files=all); then
  :
else
  die 'kernel source status check failed'
fi
[[ -z $kernel_status ]] || die 'kernel source is dirty'
[[ $(git -C "$kernel_source" rev-parse HEAD) == "$kernel_head" ]] || die 'kernel source head differs'
[[ $(git -C "$kernel_source" rev-parse 'HEAD^{tree}') == "$kernel_tree" ]] || die 'kernel source tree differs'

[[ $(live_head https://github.com/vllm-project/vllm.git) == "$vllm_head" ]] || die 'vLLM main advanced before recovery'
[[ $(live_head https://github.com/vllm-project/vllm-xpu-kernels.git) == "$kernel_head" ]] || die 'kernel main advanced before recovery'
[[ $(docker_cmd buildx imagetools inspect "$base_tag" --format '{{.Manifest.Digest}}') == "$base_digest" ]] || die 'nightly advanced before recovery'

[[ -d $build_root ]] || die 'build root is absent'
[[ $(findmnt -n -o FSTYPE --target "$build_root") == ext4 ]] || die 'build root is not ext4'
archive_parent=$(dirname -- "$archive_dir")
archive_leaf=$(basename -- "$archive_dir")
canonical_archive_parent=$(realpath -e -- "$archive_parent")
[[ $archive_dir == "$canonical_archive_parent/$archive_leaf" ]] || die 'archive path is not canonical'
[[ $archive_stage == "$canonical_archive_parent/${archive_leaf}.recovery-partial" ]] || die 'archive staging path is not canonical'
[[ $(findmnt -n -o FSTYPE --target "$canonical_archive_parent") == fuseblk ]] || die 'archive parent is not the expected inert NTFS volume'
[[ ! -e $archive_dir && ! -e $archive_stage ]] || die 'recovery archive destination already exists'
[[ ! -e $build_receipt && ! -e $failure_snapshot ]] || die 'build root was already recovered'

root_free_kib=$(df -Pk / | awk 'NR == 2 {print $4}')
[[ $root_free_kib =~ ^[0-9]+$ ]] || die 'root free-space value is invalid'
(( root_free_kib >= minimum_root_free_kib )) || die 'root has less than the 12-GiB recovery floor'
verify_quiescent_docker

verify_sha "$build_script" "$build_script_sha"
verify_sha "$dockerfile" "$dockerfile_sha"
verify_sha "$source_identity" "$source_identity_sha"
verify_sha "$source_archive" "$source_archive_sha"
verify_sha "$wheel" "$wheel_sha"
verify_sha "$log_dir/vllm-wheel-build.log" "$wheel_log_sha"
verify_sha "$log_dir/current-vllm-stock-kernel-image-build.log" "$control_log_sha"
verify_sha "$log_dir/both-current-zero-overlay-image-build.log" "$both_log_sha"
verify_sha "$receipt_dir/current-vllm-stock-kernel-image-inspect.json" "$control_inspect_sha"
verify_sha "$receipt_dir/both-current-zero-overlay-image-inspect.json" "$both_inspect_sha"
verify_sha "$receipt_dir/current-vllm-stock-kernel-static-preflight.txt" "$control_preflight_sha"
verify_sha "$receipt_dir/both-current-zero-overlay-static-preflight.txt" "$both_preflight_sha"
verify_sha "$receipt_dir/current-vllm-stock-kernel-image-tag.txt" "$control_tag_sha"
verify_sha "$receipt_dir/both-current-zero-overlay-image-tag.txt" "$empty_sha"

jq -e \
  --arg vllm_head "$vllm_head" --arg vllm_tree "$vllm_tree" \
  --arg kernel_head "$kernel_head" --arg kernel_tree "$kernel_tree" \
  --arg base_digest "$base_digest" --arg build_lab_head "$build_lab_head" \
  --arg build_lab_tree "$build_lab_tree" --arg build_utc "$build_utc" \
  --arg source_archive_sha "$source_archive_sha" \
  --arg vllm_version "$vllm_version" '
    .schema == "neural-download-absolute-current-main-source-v1" and
    .state == "built-not-gpu-qualified" and .overlay == "none" and
    .build_utc == $build_utc and .base_digest == $base_digest and
    .lab.head == $build_lab_head and .lab.tree == $build_lab_tree and
    .vllm.head == $vllm_head and .vllm.tree == $vllm_tree and
    .vllm.archive_sha256 == $source_archive_sha and
    .vllm.package_version == $vllm_version and
    .kernel.head == $kernel_head and .kernel.tree == $kernel_tree and
    .performance_floors_tok_s.tp1.diagnostic == 30.2178 and
    .performance_floors_tok_s.tp1.strict == 30.31067504052998 and
    .performance_floors_tok_s.tp2.diagnostic == 48.8301 and
    .performance_floors_tok_s.tp2.strict == 49.01965141150585 and
    .performance_floors_tok_s.tp4.diagnostic == 71.5488 and
    .performance_floors_tok_s.tp4.strict_floor == 71.29326283364946 and
    .performance_floors_tok_s.tp4.required_repeat_high == 71.39843006187554
  ' "$source_identity" >/dev/null || die 'source identity differs'

[[ $(unzip -p "$wheel" '*/METADATA' | awk -F': ' '$1 == "Name" {print $2; exit}') == vllm ]] || die 'wheel name differs'
[[ $(unzip -p "$wheel" '*/METADATA' | awk -F': ' '$1 == "Version" {print $2; exit}') == "$vllm_version" ]] || die 'wheel version differs'

if kernel_wheel_output=$(find "$kernel_artifact_dir" -type f -name '*.whl' -print); then
  :
else
  die 'official kernel wheel scan failed'
fi
kernel_wheels=()
if [[ -n $kernel_wheel_output ]]; then
  mapfile -t kernel_wheels <<<"$kernel_wheel_output"
fi
[[ ${#kernel_wheels[@]} -eq 1 ]] || die 'official kernel wheel count differs'
verify_sha "${kernel_wheels[0]}" "$kernel_wheel_sha"
verify_sha "$kernel_artifact_dir/build_info.txt" "$kernel_build_info_sha"
verify_sha "$kernel_source/.github/workflows/wheel-per-commit.yaml" "$kernel_workflow_sha"
verify_sha "$kernel_source/csrc/xpu/attn/kernel_configs/chunk_prefill_full.conf" "$chunk_sha"
verify_sha "$kernel_source/csrc/xpu/attn/kernel_configs/paged_decode_full.conf" "$paged_sha"
unzip -t "$wheel" >/dev/null || die 'vLLM wheel ZIP integrity failed'
unzip -t "${kernel_wheels[0]}" >/dev/null || die 'kernel wheel ZIP integrity failed'
[[ $(unzip -p "${kernel_wheels[0]}" '*/METADATA' | awk -F': ' '$1 == "Name" {print $2; exit}') == vllm-xpu-kernels ]] ||
  die 'kernel wheel name differs'
[[ $(unzip -p "${kernel_wheels[0]}" '*/METADATA' | awk -F': ' '$1 == "Version" {print $2; exit}') == "$kernel_version" ]] ||
  die 'kernel wheel version differs'
verify_protected_values
verify_official_kernel_artifact

verify_inspect "$receipt_dir/current-vllm-stock-kernel-image-inspect.json" \
  "$control_id" "$control_tag" current-vllm-stock-kernel \
  stock-from-base stock-from-base stock-from-base stock-from-base stock-from-base
verify_inspect "$receipt_dir/both-current-zero-overlay-image-inspect.json" \
  "$both_id" "$both_tag" both-current-zero-overlay \
  "$kernel_head" "$kernel_tree" "$kernel_wheel_sha" "$chunk_sha" "$paged_sha"
verify_tag_binding "$control_tag" "$control_id"
verify_tag_binding "$both_tag" "$both_id"

recovery_script_sha=$(sha256sum "$script_path" | awk '{print $1}')
verify_packet_binding

tmp_dir=$(mktemp -d /home/steve/qwen38-6a9c-recovery.XXXXXX)
failure_snapshot_tmp=$tmp_dir/build-failure-snapshot.json
both_tag_tmp=$tmp_dir/both-current-zero-overlay-image-tag.txt
build_receipt_tmp=$tmp_dir/build-receipt.json
cleanup_tmp() {
  find "$tmp_dir" -type f -delete 2>/dev/null || true
  rmdir "$tmp_dir" 2>/dev/null || true
}
trap cleanup_tmp EXIT

docker_cmd image inspect "$control_id" >"$tmp_dir/control-live.json"
docker_cmd image inspect "$both_id" >"$tmp_dir/both-live.json"
verify_inspect "$tmp_dir/control-live.json" \
  "$control_id" "$control_tag" current-vllm-stock-kernel \
  stock-from-base stock-from-base stock-from-base stock-from-base stock-from-base
verify_inspect "$tmp_dir/both-live.json" \
  "$both_id" "$both_tag" both-current-zero-overlay \
  "$kernel_head" "$kernel_tree" "$kernel_wheel_sha" "$chunk_sha" "$paged_sha"

for spec in "control:$control_id" "both:$both_id"; do
  name=${spec%%:*}
  image_id=${spec#*:}
  docker_cmd run --rm --pull=never --network=none --entrypoint /bin/bash "$image_id" -lc \
    'test ! -e /dev/dri; cat /opt/neural-download/import-receipt.json; cat /opt/neural-download/pip-check.txt' \
    >"$tmp_dir/$name-preflight.txt"
  cmp -s "$tmp_dir/$name-preflight.txt" "$receipt_dir/$(if [[ $name == control ]]; then printf current-vllm-stock-kernel; else printf both-current-zero-overlay; fi)-static-preflight.txt" ||
    die "$name static preflight changed"
  docker_cmd run --rm --pull=never --network=none --entrypoint /bin/bash "$image_id" -lc '
    set -Eeuo pipefail
    if test -e /workspace/vllm || test -L /workspace/vllm; then
      test -d /workspace/vllm
      test ! -L /workspace/vllm
      workspace_entry=$(find /workspace/vllm -mindepth 1 -print -quit)
      test -z "$workspace_entry"
    fi
    test -f /opt/neural-download/source-identity.json
    test ! -L /opt/neural-download/source-identity.json
    cat /opt/neural-download/source-identity.json
  ' >"$tmp_dir/$name-source-identity.json"
  cmp -s "$tmp_dir/$name-source-identity.json" "$source_identity" || die "$name in-image source identity changed"
done

recovered_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
jq -n \
  --arg recovered_utc "$recovered_utc" \
  --arg recovery_script "$script_path" --arg recovery_script_sha "$recovery_script_sha" \
  --arg build_root "$build_root" --arg archive_dir "$archive_dir" \
  --arg control_id "$control_id" --arg both_id "$both_id" \
  --arg empty_tag_sha "$empty_sha" --arg stderr 'printf: write error: No space left on device' \
  --argjson root_free_kib_after_cleanup "$root_free_kib" '
    {
      schema: "neural-download-absolute-current-main-enospc-boundary-v1",
      classification: "incomplete-after-both-static-preflights-before-tag-receipt",
      build_root: $build_root,
      intended_archive: $archive_dir,
      observed_failure_utc: "2026-08-24T19:02:17Z",
      exact_stderr: $stderr,
      original_root_free_kib_at_failure: 0,
      root_free_kib_after_cache_cleanup: $root_free_kib_after_cleanup,
      image_ids: {control: $control_id, both_current: $both_id},
      completed_before_failure: ["both image exports", "both image inspections", "both static preflights"],
      absent_before_recovery: ["aggregate build receipt", "external archive"],
      both_tag_receipt_before_recovery: {size_bytes: 0, sha256: $empty_tag_sha},
      gpu_or_model_work_ran: false,
      recovery: {utc: $recovered_utc, script: $recovery_script, script_sha256: $recovery_script_sha}
    }
  ' >"$failure_snapshot_tmp"
jq empty "$failure_snapshot_tmp" || die 'failure snapshot JSON is invalid'
failure_snapshot_sha=$(sha256sum "$failure_snapshot_tmp" | awk '{print $1}')

printf '%s\n' "$both_tag" >"$both_tag_tmp"
verify_sha "$both_tag_tmp" "$both_tag_recovered_sha"

jq -n \
  --arg archive_dir "$archive_dir" --arg base_digest "$base_digest" \
  --arg build_root "$build_root" --arg build_utc "$build_utc" \
  --arg build_script_sha "$build_script_sha" --arg dockerfile_sha "$dockerfile_sha" \
  --arg build_lab_head "$build_lab_head" --arg build_lab_tree "$build_lab_tree" \
  --arg vllm_head "$vllm_head" --arg vllm_tree "$vllm_tree" \
  --arg vllm_version "$vllm_version" --arg source_archive_sha "$source_archive_sha" \
  --arg wheel_sha "$wheel_sha" --arg kernel_head "$kernel_head" \
  --arg kernel_tree "$kernel_tree" --arg kernel_version "$kernel_version" \
  --arg kernel_artifact_name "$kernel_artifact_name" \
  --arg kernel_artifact_digest "$kernel_artifact_digest" \
  --arg kernel_wheel_sha "$kernel_wheel_sha" \
  --arg kernel_build_info_sha "$kernel_build_info_sha" \
  --arg kernel_workflow_sha "$kernel_workflow_sha" \
  --arg chunk_sha "$chunk_sha" --arg paged_sha "$paged_sha" \
  --arg rust_extension_sha "$rust_extension_sha" --arg rust_frontend_sha "$rust_frontend_sha" \
  --arg control_tag "$control_tag" --arg control_id "$control_id" \
  --arg control_preflight_sha "$control_preflight_sha" --arg both_tag "$both_tag" \
  --arg both_id "$both_id" --arg both_preflight_sha "$both_preflight_sha" \
  --arg recovered_utc "$recovered_utc" --arg recovery_script_sha "$recovery_script_sha" \
  --arg failure_snapshot_sha "$failure_snapshot_sha" \
  --arg recovery_lab_head "$recovery_lab_head" --arg recovery_lab_tree "$recovery_lab_tree" \
  --argjson kernel_run_id "$kernel_run_id" --argjson kernel_artifact_id "$kernel_artifact_id" \
  --argjson kernel_artifact_size "$kernel_artifact_size" '
    {
      schema: "neural-download-absolute-current-main-build-v1",
      state: "static-preflight-passed-for-built-images-gpu-qualification-pending",
      mode: "--build-all",
      overlay: "none",
      build_utc: $build_utc,
      build_root: $build_root,
      external_archive: $archive_dir,
      base_digest: $base_digest,
      lab: {head: $build_lab_head, tree: $build_lab_tree},
      build_inputs: {script_sha256: $build_script_sha, dockerfile_sha256: $dockerfile_sha},
      reused_rust: {
        source_equivalence_base: "f94666b60d4c58ec0807d22c837cfae322a1dde9",
        extension_sha256: $rust_extension_sha,
        frontend_sha256: $rust_frontend_sha
      },
      vllm: {
        head: $vllm_head,
        tree: $vllm_tree,
        package_version: $vllm_version,
        source_archive_sha256: $source_archive_sha,
        wheel_sha256: $wheel_sha
      },
      kernel: {
        head: $kernel_head,
        tree: $kernel_tree,
        package_version: $kernel_version,
        official_artifact: {
          run_id: $kernel_run_id,
          artifact_id: $kernel_artifact_id,
          name: $kernel_artifact_name,
          archive_digest: $kernel_artifact_digest,
          archive_size_bytes: $kernel_artifact_size,
          wheel_sha256: $kernel_wheel_sha,
          build_info_sha256: $kernel_build_info_sha,
          workflow_sha256: $kernel_workflow_sha,
          chunk_prefill_full_sha256: $chunk_sha,
          paged_decode_full_sha256: $paged_sha
        }
      },
      images: {
        current_vllm_stock_kernel: {
          built: true,
          tag: $control_tag,
          image_id: $control_id,
          static_preflight_passed: true,
          static_preflight_sha256: $control_preflight_sha
        },
        both_current_zero_overlay: {
          built: true,
          tag: $both_tag,
          image_id: $both_id,
          static_preflight_passed: true,
          static_preflight_sha256: $both_preflight_sha
        }
      },
      receipt_recovery: {
        required: true,
        cause: "Both image exports, inspections, and static preflights completed; ENOSPC stopped the normal writer at the both-current tag receipt, before the aggregate receipt and archive.",
        recovered_utc: $recovered_utc,
        recovery_script_sha256: $recovery_script_sha,
        build_failure_snapshot: "build-failure-snapshot.json",
        build_failure_snapshot_sha256: $failure_snapshot_sha,
        recovery_lab: {head: $recovery_lab_head, tree: $recovery_lab_tree},
        method: "Revalidated immutable image IDs and labels, source/archive/wheel/build-input hashes, stored and rerun static preflights, exact kernel artifact, clean pushed lab main, and unchanged live vLLM/kernel/nightly identities. No image, source, overlay, performance gate, model, or GPU state changed.",
        freshness: {
          vllm_upstream_main: $vllm_head,
          vllm_xpu_kernels_upstream_main: $kernel_head,
          official_nightly_index_digest: $base_digest
        }
      },
      promotion: {
        qualified: false,
        order: [
          "current-vLLM/stock-kernel TP1",
          "both-current zero-overlay TP1",
          "both-current accepted-overlay TP1",
          "TP2",
          "TP4"
        ],
        rule: "Never replace a certified result unless identity, quality, and performance floors all pass."
      }
    }
  ' >"$build_receipt_tmp"
jq -e '
  .schema == "neural-download-absolute-current-main-build-v1" and
  .state == "static-preflight-passed-for-built-images-gpu-qualification-pending" and
  .mode == "--build-all" and .overlay == "none" and
  .receipt_recovery.required == true and .promotion.qualified == false
' "$build_receipt_tmp" >/dev/null || die 'recovered build receipt JSON is invalid'

mkdir -- "$archive_stage"
cp -- "$wheel" "$archive_stage/"
cp -- "$build_receipt_tmp" "$archive_stage/build-receipt.json"
cp -- "$failure_snapshot_tmp" "$archive_stage/build-failure-snapshot.json"
cp -- "$both_tag_tmp" "$archive_stage/both-current-zero-overlay-image-tag.txt"
cp -- "$source_identity" "$archive_stage/"
cp -- "$build_script" "$archive_stage/"
cp -- "$dockerfile" "$archive_stage/"
cp -- "$script_path" "$archive_stage/"
cp -- "$attempt_record" "$archive_stage/"
cp -- "$prereg" "$archive_stage/"
cp -- "$receipt_dir/current-vllm-stock-kernel-image-inspect.json" "$archive_stage/"
cp -- "$receipt_dir/current-vllm-stock-kernel-image-tag.txt" "$archive_stage/"
cp -- "$receipt_dir/current-vllm-stock-kernel-static-preflight.txt" "$archive_stage/"
cp -- "$receipt_dir/both-current-zero-overlay-image-inspect.json" "$archive_stage/"
cp -- "$receipt_dir/both-current-zero-overlay-static-preflight.txt" "$archive_stage/"
find "$log_dir" -maxdepth 1 -type f -exec cp -t "$archive_stage" -- {} +
(
  cd "$archive_stage"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -printf '%P\n' |
    sort | xargs -r sha256sum >SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)

verify_sha "$archive_stage/$(basename -- "$wheel")" "$wheel_sha"
verify_sha "$archive_stage/$(basename -- "$source_identity")" "$source_identity_sha"
verify_sha "$archive_stage/$(basename -- "$build_script")" "$build_script_sha"
verify_sha "$archive_stage/$(basename -- "$dockerfile")" "$dockerfile_sha"
verify_sha "$archive_stage/$(basename -- "$script_path")" "$recovery_script_sha"
verify_sha "$archive_stage/current-vllm-stock-kernel-image-inspect.json" "$control_inspect_sha"
verify_sha "$archive_stage/current-vllm-stock-kernel-image-tag.txt" "$control_tag_sha"
verify_sha "$archive_stage/current-vllm-stock-kernel-static-preflight.txt" "$control_preflight_sha"
verify_sha "$archive_stage/both-current-zero-overlay-image-inspect.json" "$both_inspect_sha"
verify_sha "$archive_stage/both-current-zero-overlay-image-tag.txt" "$both_tag_recovered_sha"
verify_sha "$archive_stage/both-current-zero-overlay-static-preflight.txt" "$both_preflight_sha"
verify_sha "$archive_stage/vllm-wheel-build.log" "$wheel_log_sha"
verify_sha "$archive_stage/current-vllm-stock-kernel-image-build.log" "$control_log_sha"
verify_sha "$archive_stage/both-current-zero-overlay-image-build.log" "$both_log_sha"
cmp -s "$archive_stage/$(basename -- "$attempt_record")" "$attempt_record" ||
  die 'archived build-attempt record differs'
cmp -s "$archive_stage/$(basename -- "$prereg")" "$prereg" ||
  die 'archived recovery preregistration differs'
cmp -s "$archive_stage/build-failure-snapshot.json" "$failure_snapshot_tmp" ||
  die 'archived failure snapshot differs'
cmp -s "$archive_stage/build-receipt.json" "$build_receipt_tmp" ||
  die 'archived build receipt differs'

[[ $(live_head https://github.com/vllm-project/vllm.git) == "$vllm_head" ]] || die 'vLLM main advanced during recovery'
[[ $(live_head https://github.com/vllm-project/vllm-xpu-kernels.git) == "$kernel_head" ]] || die 'kernel main advanced during recovery'
[[ $(docker_cmd buildx imagetools inspect "$base_tag" --format '{{.Manifest.Digest}}') == "$base_digest" ]] || die 'nightly advanced during recovery'
[[ $(git -C "$repo" rev-parse HEAD) == "$recovery_lab_head" ]] || die 'lab HEAD moved during recovery'
[[ $(git -C "$repo" rev-parse 'HEAD^{tree}') == "$recovery_lab_tree" ]] || die 'lab tree moved during recovery'
[[ $(git -C "$repo" rev-parse origin/main) == "$recovery_lab_head" ]] || die 'local lab origin/main moved during recovery'
if lab_status_post=$(git -C "$repo" status --porcelain=v1 --untracked-files=all); then
  :
else
  die 'postflight lab repo status check failed'
fi
[[ -z $lab_status_post ]] || die 'lab repo changed during recovery'
[[ $(live_head git@github.com:steveseguin/b70-optimization-lab.git) == "$recovery_lab_head" ]] || die 'live lab origin/main moved during recovery'
[[ $(git -C "$vllm_source" rev-parse HEAD) == "$vllm_head" ]] || die 'vLLM source head moved during recovery'
[[ $(git -C "$vllm_source" rev-parse 'HEAD^{tree}') == "$vllm_tree" ]] || die 'vLLM source tree moved during recovery'
if vllm_status_post=$(git -C "$vllm_source" status --porcelain=v1 --untracked-files=all); then
  :
else
  die 'postflight vLLM source status check failed'
fi
[[ -z $vllm_status_post ]] || die 'vLLM source changed during recovery'
[[ $(git -C "$kernel_source" rev-parse HEAD) == "$kernel_head" ]] || die 'kernel source head moved during recovery'
[[ $(git -C "$kernel_source" rev-parse 'HEAD^{tree}') == "$kernel_tree" ]] || die 'kernel source tree moved during recovery'
if kernel_status_post=$(git -C "$kernel_source" status --porcelain=v1 --untracked-files=all); then
  :
else
  die 'postflight kernel source status check failed'
fi
[[ -z $kernel_status_post ]] || die 'kernel source changed during recovery'
verify_frozen_evidence
verify_official_kernel_artifact
verify_packet_binding
verify_sha "$both_tag_tmp" "$both_tag_recovered_sha"
verify_tag_binding "$control_tag" "$control_id"
verify_tag_binding "$both_tag" "$both_id"
docker_cmd image inspect "$control_id" >"$tmp_dir/control-live-post.json"
docker_cmd image inspect "$both_id" >"$tmp_dir/both-live-post.json"
verify_inspect "$tmp_dir/control-live-post.json" \
  "$control_id" "$control_tag" current-vllm-stock-kernel \
  stock-from-base stock-from-base stock-from-base stock-from-base stock-from-base
verify_inspect "$tmp_dir/both-live-post.json" \
  "$both_id" "$both_tag" both-current-zero-overlay \
  "$kernel_head" "$kernel_tree" "$kernel_wheel_sha" "$chunk_sha" "$paged_sha"
verify_quiescent_docker
root_free_kib_post=$(df -Pk / | awk 'NR == 2 {print $4}')
[[ $root_free_kib_post =~ ^[0-9]+$ ]] || die 'postflight root free-space value is invalid'
(( root_free_kib_post >= minimum_root_free_kib )) || die 'postflight root free space fell below 12 GiB'

mv -T -- "$archive_stage" "$archive_dir"
mv -T -- "$failure_snapshot_tmp" "$failure_snapshot"
mv -T -- "$both_tag_tmp" "$receipt_dir/both-current-zero-overlay-image-tag.txt"
mv -T -- "$build_receipt_tmp" "$build_receipt"
cmp -s "$build_receipt" "$archive_dir/build-receipt.json" || die 'archived receipt differs'
(
  cd "$archive_dir"
  sha256sum -c SHA256SUMS >/dev/null
)
sync -f "$receipt_dir"
sync -f "$archive_dir"

printf 'PASS: 6a9c ENOSPC receipt recovered without rebuilding or GPU work\n'
printf '  receipt: %s\n' "$build_receipt"
printf '  archive: %s\n' "$archive_dir"
printf '  receipt sha256: %s\n' "$(sha256sum "$build_receipt" | awk '{print $1}')"
printf '  archive SHA256SUMS sha256: %s\n' "$(sha256sum "$archive_dir/SHA256SUMS" | awk '{print $1}')"
