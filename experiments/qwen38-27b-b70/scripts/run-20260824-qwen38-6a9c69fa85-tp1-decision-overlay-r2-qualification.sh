#!/usr/bin/env bash
set -Eeuo pipefail

# Atomic overlay-only TP1 qualification for literal-current vLLM 6a9c69fa85.
# The untreated parent and failed-incomplete r1 predecessor are sealed. This
# wrapper verifies both byte-for-byte, runs a fresh current-commit hardware
# gate, then seeds only 38 compatible best_config decisions into a new cache.

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
lane=$repo/experiments/qwen38-27b-b70
runner=$lane/scripts/run-20260824-qwen38-known-nvme-aware-strict-smoke.sh
kernel_delta_classifier=$lane/scripts/classify-20260824-kernel-delta.py
kernel_delta_classifier_test=$lane/tests/test_classify_20260824_kernel_delta.py
classifier_test_python=/home/steve/.venvs/vllm-xpu/bin/python
hardware_gate_runner=$lane/scripts/run-20260824-qwen38-known-nvme-aware-hardware-gate.sh
receipt=$lane/data/2026-08-24-qwen38-6a9c69fa85-absolute-current-main-build.json
suite=$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json
baseline=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json
model_manifest=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json
model_verifier=$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py
bench_helper=$repo/scripts/bench-openai-realistic-suite.py
quality_helper=$repo/scripts/qwen38-text-quality-suite.py
prereg=$lane/notes/2026-08-24-qwen38-6a9c69fa85-tp1-decision-overlay-r2-prereg.md
parent_record=$lane/data/2026-08-24-qwen38-6a9c69fa85-tp1-r1-speed-only-miss.json
parent_closeout=$lane/notes/2026-08-24-qwen38-6a9c69fa85-tp1-r1-speed-only-miss.md
stale_record=$lane/data/2026-08-24-qwen38-6a9c69fa85-tp1-decision-overlay-r1-live-lab-stale.json
stale_closeout=$lane/notes/2026-08-24-qwen38-6a9c69fa85-tp1-decision-overlay-r1-live-lab-stale.md
protected_manifest=$lane/data/2026-08-23-qwen38-current-main-overlay-manifest.json
tp2_overlay=$lane/autotune-winner-overlays/tp2-e9d1398-best-config
tp4_overlay=$lane/autotune-winner-overlays/tp4-e9d1398-best-config
overlay=$lane/autotune-winner-overlays/tp1-6a9c69fa85-stock-kernel-best-config-compatible-r1
seed_source=$overlay/source
overlay_manifest=$overlay/manifest.sha256
overlay_metadata=$overlay/metadata.json
overlay_readme=$overlay/README.md
overlay_census=$overlay/compatibility-census.tsv

readonly parent_hardware=/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-6a9c69fa85-20260824-086de284-venvlib-r1
readonly parent_root=/home/steve/qwen38-current-main-runs/tp1-untreated-6a9c69fa85-20260824-r1
readonly parent_cache=$parent_root/control-cache
readonly parent_fresh_out=$parent_root/control-fresh-diagnostic
readonly parent_replay_a_out=$parent_root/control-strict-quality-replay-a
readonly parent_replay_b_out=$parent_root/control-strict-replay-b
readonly stale_hardware=/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-6a9c69fa85-overlay-20260824-086de284-venvlib-r1
readonly stale_root=/home/steve/qwen38-current-main-runs/tp1-control-decision-overlay-6a9c69fa85-20260824-r1
readonly stale_cache=$stale_root/overlay-cache
readonly stale_fresh_out=$stale_root/seeded-fresh-diagnostic
readonly hardware_gate=/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-6a9c69fa85-overlay-20260824-086de284-venvlib-r2
readonly result_root=/home/steve/qwen38-current-main-runs/tp1-control-decision-overlay-6a9c69fa85-20260824-r2
inputs=$result_root/inputs
overlay_cache=$result_root/overlay-cache
fresh_out=$result_root/seeded-fresh-diagnostic
replay_a_out=$result_root/strict-quality-replay-a
replay_b_out=$result_root/strict-replay-b
frozen_inputs_manifest_sha256=
frozen_overlay_cache_manifest_sha256=
frozen_overlay_directory_manifest_sha256=
classifier_test_receipt=
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}

expected_suite_sha256=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
expected_baseline_sha256=738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18
expected_receipt_sha256=a7b2d9a4fa1693c4ca83e98a494b249a380087963702c0f30cf558bb889400f3
expected_prereg_sha256=67f60a5a8eeb76dcd81844abbf93c0478441a083ce0491490c0302af4cf32d6b
expected_runner_sha256=49c49932e684de445a59293c13abb5a36de9b2878e697cbacd7462d6201a1fbb
expected_kernel_delta_classifier_sha256=fef74bdb90b82fdf543be6ea36320b308aff0d0c146a3c92bcbfff334b70d1b0
expected_kernel_delta_classifier_test_sha256=b21befd70003b710027303e093915c36ce88d8fcd4eda66facfd549057e5474b
expected_hardware_gate_runner_sha256=8038015b179048662f53d7d41ead6cddc95671081942444f394c6e48ed57a6f7
expected_parent_record_sha256=5068d6b035deb02395780e5bebf34b6b81082be08029293547acbb4507902784
expected_parent_closeout_sha256=becac5747b289dfea5923b868ccc26a5589b6d7b525f741d330c6b6f3bf8c3d6
expected_stale_record_sha256=c9b20b3360fc24c45a8f116cb6b2f6c7cca12b66d842475e13fb71a62c983e5b
expected_stale_closeout_sha256=286525a8017c03bf09c69f8f290a5bf2b36da1673130331550a0f3ca3b1d4d57
expected_stale_campaign_manifest_sha256=3098ab384aea4f76995498f8f8a83eb93732b4b61aa5e80dd4ee3df5d21f8196
expected_stale_inputs_manifest_sha256=db58dad8b6f5be7d26703abbd8652d2c8ead4d11e4599091e376c9b07e8bc5ca
expected_stale_failure_sha256=e03a24950951e1ab2b3dc0658ec4bc0a95b085d84c9c277e25be3823c4b1bb00
expected_stale_final_status_sha256=2407e0ccc37ff46223e5b09ae2e34d598c71c0d95d3e7b12990982fc7c788c15
expected_stale_bench_sha256=4c81b37d145372ec491ac0d7fc1f4b4e944b5e4ada9276ba936e6d670d07917e
expected_stale_cache_manifest_sha256=9f9f4e03dc3fb023ec66f983789834424e69bd0351b32e7502beae0a5113347e
expected_stale_directory_manifest_sha256=c27d308f3721467d344d89fa9fcee333bea20e9bddbac35603217d6d3c6b9298
expected_stale_hardware_manifest_sha256=3432fc6536b36f02f086f34e55663f7515e6057c192b0c85320e73cefd3abb00
expected_stale_hardware_summary_sha256=e02dae560c81108bb1e6a79dbefb4a32a48791c0e99e8d44019285a990faef16
expected_stale_wrapper_sha256=1ee7261ec643ae35adae2c9161ff722c04026c73dde74a958b3bb8a4dfc99b04
expected_stale_prereg_sha256=c8d85e53f6aa0f17a98d10c587d895f453d57b5946fd3528e54de1e231f5f679
expected_protected_manifest_sha256=654e355de4799a8c58ae00cd6b1e45c8e4dc51fc3b7a3b4164c14d74d1716be9
expected_seed_manifest_sha256=b941bb71c1d264dcd55104b106b2dff6a85c686776b072e0ef6cc18a8354c928
expected_overlay_metadata_sha256=33606d3d0f93a31e4d68b430414116e39cb6bb394dc1f3a5c5dfb3c1bfcb5b29
expected_overlay_readme_sha256=09c5ac484afea6e9b5aedd3822d4af1b69ea35ec0c9b80da16910007386b72cc
expected_overlay_census_sha256=f3477beba643f0136d71388e54a3a539ab067b716a7db9750b0131b457b03d03
expected_seed_count=38
expected_parent_campaign_manifest_sha256=ecc882372a9408ede3e660d56a6ed9e986adf2d748199e9caa331fd57ef00e10
expected_parent_inputs_manifest_sha256=e493930467912721f58422afef5a6ebe2494bae1288f251500efe4536a17b28b
expected_parent_result_sha256=fc4c81bdf75dd632c60bde47865272e5f63a0a21e457abe5de4bc2cc9ef2b213
expected_parent_cache_manifest_sha256=4a41a96bb1ddb9c5a96d476c11bca89278742a61f9b20aace40cfbcec39364a4
expected_parent_hardware_manifest_sha256=b15e94a256fcc4870edfa21240d0230fcd4ee7a7329cc33feb2a81f5f01cadbe
expected_parent_hardware_summary_sha256=83de8cc81972bb44d2ccc972f2143effbb964becdfc06fdc9cdf7a0f87c52e54
expected_parent_hardware_status_sha256=ed163d69a09ddc0ffcbdf126a42d5745a93449fa7a39354788e948b7ac795c04
expected_protected_values_sha256=e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f
expected_tp2_manifest_sha256=65c574c24d24804d250e5179e9a202ec9e77e8c5740cea121b7660d8ee854757
expected_tp4_manifest_sha256=a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2

expected_vllm_head=6a9c69fa851389dcf1ee5d3a2363e27af665d26d
expected_vllm_tree=baf2301fb3f993537b07b6132b4d980efca2e7e4
expected_kernel_head=baaa05bb4e92901219a5a072dd63f2474896f6d1
expected_kernel_tree=e7e7d1063f232a383c98c1820cebb94c45b4906e
expected_base_digest=sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876
expected_control_image_id=sha256:24ca5f6b6e5a14f71f43f82469f6e9debd36b2965942932e1646f377e30799cf
expected_both_image_id=sha256:f86c4c78d76a484f5d54eda310419c91a2471634ab97782022ef7573fc19a7d9
expected_host_kernel=7.0.0-30-generic
expected_host_boot_id=086de284-0771-4269-9cb2-e064fe303e40
expected_outer_namespace=1698e8221e
expected_aot_namespace=3be24aa9230ff903e8d2dc977dbd63e1cdac51c2f9086ca264135826fd81d61b
expected_code_hash=fb13d4aa1ef8a386c76ab56d39925ff4de083895d9dcbd136e778046e78bb118
expected_compiler_hash=ddcad03736
expected_config_hash=006ac9802b
expected_env_sha256=a048dd409b16d2004c6ec4c534e0e954c304ed2cd5bebe6d8bc39be9cb7d7c7b
expected_graph_sha256=f493f62d98181193e6760136123c70511e9a0a7f1d91cbf3243008a619553339
diagnostic_floor=30.2178
strict_floor=30.31067504052998

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

for command_name in awk chmod cmp cp df docker env find findmnt flock git grep \
  jq mv pgrep realpath rg sed sha256sum sort stat sudo sync timeout tr uname \
  unzip wc xargs; do
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
  local root=$1 manifest_sha=$2 count=$3 actual_count symlink_output
  [[ -d $root/source && -f $root/manifest.sha256 ]] ||
    die "overlay payload is incomplete: $root"
  [[ $(sha256sum "$root/manifest.sha256" | awk '{print $1}') == \
     "$manifest_sha" ]] || die "overlay manifest changed: $root"
  actual_count=$(find "$root/source" -type f | wc -l)
  [[ $actual_count == "$count" ]] || die "overlay file count changed: $root"
  [[ $(find "$root/source" -type f -name '*.best_config' | wc -l) == \
     "$count" ]] || die "overlay contains a non-best_config file: $root"
  symlink_output=$(find "$root" -type l -print -quit) ||
    die "overlay symlink scan failed: $root"
  [[ -z $symlink_output ]] || die "overlay contains a symlink: $root"
  (
    cd "$root/source"
    sha256sum -c ../manifest.sha256 >/dev/null
  ) || die "overlay payload checksum failed: $root"
}

verify_protected_values() {
  local actual_protected_values_sha
  [[ $(sha256sum "$protected_manifest" | awk '{print $1}') == \
     "$expected_protected_manifest_sha256" ]] ||
    die 'protected manifest file changed'
  actual_protected_values_sha=$(
    jq -cS '.protected_target_only_decode_tok_s' "$protected_manifest" |
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
    .protected_target_only_decode_tok_s.a356_tp2_decision_overlay_diagnostic == [49.05894025767351] and
    .protected_target_only_decode_tok_s.a356_tp2_decision_overlay_strict == [49.00935245117815] and
    .protected_target_only_decode_tok_s.a356_tp4_decision_overlay_diagnostic == [71.72254506718171] and
    .protected_target_only_decode_tok_s.a356_tp4_decision_overlay_strict == [71.35287190161719, 71.45427094575045]
  ' "$protected_manifest" >/dev/null || die 'protected performance values changed'
  verify_overlay_payload "$tp2_overlay" "$expected_tp2_manifest_sha256" 78
  verify_overlay_payload "$tp4_overlay" "$expected_tp4_manifest_sha256" 152
}

verify_decision_bundle() {
  local top_files census_rows total_files unexpected_node unexpected_directory
  for required in "$overlay_manifest" "$overlay_metadata" "$overlay_readme" \
      "$overlay_census"; do
    [[ -f $required ]] || die "decision-bundle input is absent: $required"
  done
  [[ $(sha256sum "$overlay_metadata" | awk '{print $1}') == \
     "$expected_overlay_metadata_sha256" ]] || die 'decision metadata changed'
  [[ $(sha256sum "$overlay_readme" | awk '{print $1}') == \
     "$expected_overlay_readme_sha256" ]] || die 'decision README changed'
  [[ $(sha256sum "$overlay_census" | awk '{print $1}') == \
     "$expected_overlay_census_sha256" ]] || die 'compatibility census changed'
  top_files=$(find "$overlay" -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort)
  [[ $top_files == $'README.md\ncompatibility-census.tsv\nmanifest.sha256\nmetadata.json' ]] ||
    die 'decision-bundle top-level file set changed'
  total_files=$(find "$overlay" -type f | wc -l)
  [[ $total_files == 42 ]] ||
    die 'decision bundle contains an unexpected regular file'
  unexpected_node=$(find "$overlay" -mindepth 1 ! -type f ! -type d \
    -print -quit) || die 'decision-bundle node-type scan failed'
  [[ -z $unexpected_node ]] ||
    die "decision bundle contains a special node: $unexpected_node"
  unexpected_directory=$(find "$overlay" -mindepth 1 -type d \
    ! -path "$seed_source" ! -path "$seed_source/[0-9a-z][0-9a-z]" \
    -print -quit) || die 'decision-bundle directory scan failed'
  [[ -z $unexpected_directory ]] ||
    die "decision bundle contains an unexpected directory: $unexpected_directory"
  verify_overlay_payload "$overlay" "$expected_seed_manifest_sha256" \
    "$expected_seed_count"
  census_rows=$(wc -l <"$overlay_census")
  [[ $census_rows == 39 ]] || die 'compatibility census must contain 38 data rows'
  jq -e \
    --arg vllm "$expected_vllm_head" --arg vllm_tree "$expected_vllm_tree" \
    --arg kernel "$expected_kernel_head" --arg kernel_tree "$expected_kernel_tree" \
    --arg base "$expected_base_digest" --arg image "$expected_both_image_id" \
    --arg receipt "$expected_receipt_sha256" \
    --arg parent_result "$expected_parent_result_sha256" \
    --arg parent_manifest "$expected_parent_campaign_manifest_sha256" \
    --arg parent_cache "$expected_parent_cache_manifest_sha256" \
    --arg seed_manifest "$expected_seed_manifest_sha256" \
    --arg census "$expected_overlay_census_sha256" \
    --arg outer "$expected_outer_namespace" --arg aot "$expected_aot_namespace" \
    --arg code "$expected_code_hash" --arg compiler "$expected_compiler_hash" \
    --arg config "$expected_config_hash" --arg env "$expected_env_sha256" \
    --arg graph "$expected_graph_sha256" '
    .schema == "neural-download-qwen38-autotune-decision-overlay-v2" and
    .state == "test-only-unqualified" and
    .target_parent.vllm_head == $vllm and .target_parent.vllm_tree == $vllm_tree and
    .target_parent.kernel_head == $kernel and .target_parent.kernel_tree == $kernel_tree and
    .target_parent.official_nightly_index_digest == $base and
    .target_parent.image_id == $image and
    .target_parent.build_receipt_sha256 == $receipt and
    .target_parent.aggregate_result_sha256 == $parent_result and
    .target_parent.campaign_manifest_sha256 == $parent_manifest and
    .target_parent.classification == "complete-speed-only-regression-no-overlay-run" and
    .target_parent.all_non_speed_gates_pass == true and
    .target_parent.tp2_tp4_authorized == false and
    .cache_compatibility.target.cache_manifest_sha256 == $parent_cache and
    .cache_compatibility.target.outer_namespace == $outer and
    .cache_compatibility.target.aot_namespace == $aot and
    .cache_compatibility.target.code_hash == $code and
    .cache_compatibility.target.compiler_hash == $compiler and
    .cache_compatibility.target.config_hash == $config and
    .cache_compatibility.target.canonical_environment_sha256 == $env and
    .cache_compatibility.target.computation_graph_sha256 == $graph and
    .cache_compatibility.result.source_best_config_files == 38 and
    .cache_compatibility.result.target_best_config_files == 38 and
    .cache_compatibility.result.common_relative_paths == 38 and
    .cache_compatibility.result.matching_embedded_configs_hash == 38 and
    .cache_compatibility.result.configs_hash_mismatches == 0 and
    .cache_compatibility.result.normalized_decisions_equal == 24 and
    .cache_compatibility.result.normalized_decisions_different == 14 and
    .cache_compatibility.result.byte_identical_files == 2 and
    .cache_compatibility.result.decision_seed_compatible == true and
    .cache_compatibility.result.compiled_cache_compatible == false and
    .cache_compatibility.census.sha256 == $census and
    .cache_compatibility.census.rows == 38 and
    .bundle.file_count == 38 and .bundle.manifest_sha256 == $seed_manifest and
    .bundle.historical_source_files_byte_identical == 38 and
    .bundle.compiled_binaries_included == false and
    .bundle.generated_kernels_included == false and
    .bundle.generated_python_included == false and
    .bundle.aot_model_included == false and .bundle.outer_cache_included == false and
    .qualification_rule.diagnostic_floor_tok_s == 30.2178 and
    .qualification_rule.strict_floor_tok_s == 30.31067504052998 and
    .qualification_rule.strict_replays_required == 2 and
    .qualification_rule.fresh_cache_required == true and
    .qualification_rule.floor_reduction_allowed == false and
    .qualification_rule.tp2_authorized_before_pass == false and
    .execution.executed_arms == 0 and .execution.result == null
  ' "$overlay_metadata" >/dev/null || die 'decision metadata contract changed'
}

verify_parent_campaign() {
  local parent_symlink cache_symlink cache_files cache_best_configs
  local cache_manifest
  for required in "$parent_root/campaign-evidence.sha256" \
      "$parent_root/campaign-evidence.sha256.digest" \
      "$parent_root/control-result.json" "$parent_root/control-result.sha256" \
      "$parent_root/final.status" "$parent_root/inputs/SHA256SUMS" \
      "$parent_fresh_out/cache-manifest.post.sha256" \
      "$parent_fresh_out/cache-manifest.post.sha256.digest" \
      "$parent_replay_a_out/cache-manifest.pre.sha256" \
      "$parent_replay_a_out/cache-manifest.post.sha256" \
      "$parent_replay_b_out/cache-manifest.pre.sha256" \
      "$parent_replay_b_out/cache-manifest.post.sha256" \
      "$parent_replay_a_out/quality.json" "$parent_hardware/SHA256SUMS" \
      "$parent_hardware/summary.json" "$parent_hardware/final.status"; do
    [[ -f $required ]] || die "sealed parent evidence is absent: $required"
  done
  [[ ! -L $parent_root && ! -L $parent_cache && ! -L $parent_hardware ]] ||
    die 'a sealed parent root is a symlink'
  parent_symlink=$(find "$parent_root" -path "$parent_cache" -prune -o \
    -type l -print -quit) || die 'sealed parent symlink scan failed'
  [[ -z $parent_symlink ]] || die 'sealed parent evidence contains a symlink'
  cache_symlink=$(sudo -S -p '' find "$parent_cache" -type l -print -quit \
    <"$sudo_pass_file") || die 'parent cache symlink scan failed'
  [[ -z $cache_symlink ]] || die 'parent compiled cache contains a symlink'
  [[ $(findmnt -n -o FSTYPE --target "$parent_cache") == ext4 ]] ||
    die 'sealed parent cache is no longer on ext4'

  [[ $(sha256sum "$parent_root/campaign-evidence.sha256" | awk '{print $1}') == \
     "$expected_parent_campaign_manifest_sha256" ]] ||
    die 'parent campaign manifest changed'
  [[ $(<"$parent_root/campaign-evidence.sha256.digest") == \
     "$expected_parent_campaign_manifest_sha256" ]] ||
    die 'parent campaign manifest digest file changed'
  (
    cd "$parent_root"
    sha256sum -c campaign-evidence.sha256 >/dev/null
  ) || die 'parent campaign evidence checksum failure'
  [[ $(sha256sum "$parent_root/inputs/SHA256SUMS" | awk '{print $1}') == \
     "$expected_parent_inputs_manifest_sha256" ]] ||
    die 'parent frozen-input manifest changed'
  (
    cd "$parent_root/inputs"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die 'parent frozen inputs changed'
  [[ -z $(find "$parent_root/inputs" -type f -perm /222 -print -quit) ]] ||
    die 'parent frozen input became writable'
  [[ -z $(find "$parent_root/inputs" -type d -perm /222 -print -quit) ]] ||
    die 'parent frozen input directory became writable'
  [[ $(sha256sum "$parent_root/control-result.json" | awk '{print $1}') == \
     "$expected_parent_result_sha256" &&
     $(<"$parent_root/control-result.sha256") == \
     "$expected_parent_result_sha256" ]] || die 'parent aggregate result changed'
  [[ $(<"$parent_root/final.status") == \
     complete-speed-only-regression-no-overlay-run ]] ||
    die 'parent terminal classification changed'

  for cache_manifest in "$parent_fresh_out/cache-manifest.post.sha256" \
      "$parent_replay_a_out/cache-manifest.pre.sha256" \
      "$parent_replay_a_out/cache-manifest.post.sha256" \
      "$parent_replay_b_out/cache-manifest.pre.sha256" \
      "$parent_replay_b_out/cache-manifest.post.sha256"; do
    [[ $(sha256sum "$cache_manifest" | awk '{print $1}') == \
       "$expected_parent_cache_manifest_sha256" ]] ||
      die "parent cache-manifest evidence changed: $cache_manifest"
    cmp -s "$parent_fresh_out/cache-manifest.post.sha256" "$cache_manifest" ||
      die 'parent replay cache manifests no longer agree'
  done
  [[ $(<"$parent_fresh_out/cache-manifest.post.sha256.digest") == \
     "$expected_parent_cache_manifest_sha256" ]] ||
    die 'parent cache-manifest digest changed'
  cache_files=$(sudo -S -p '' find "$parent_cache" -type f \
    <"$sudo_pass_file" | wc -l)
  cache_best_configs=$(sudo -S -p '' find "$parent_cache" -type f \
    -name '*.best_config' <"$sudo_pass_file" | wc -l)
  [[ $cache_files == 1097 && $cache_best_configs == 38 ]] ||
    die 'parent compiled-cache file counts changed'
  sudo -S -p '' bash -c '
    set -euo pipefail
    cd "$1"
    sha256sum -c "$2" >/dev/null
  ' bash "$parent_cache" "$parent_fresh_out/cache-manifest.post.sha256" \
    <"$sudo_pass_file" || die 'actual parent compiled-cache bytes changed'

  [[ $(<"$parent_fresh_out/final.status") == pass &&
     $(<"$parent_replay_a_out/final.status") == pass &&
     $(<"$parent_replay_b_out/final.status") == pass ]] ||
    die 'a parent arm final status changed'
  grep -Fx 'pass actual=30.27858669748398 floor=30.2178' \
    "$parent_fresh_out/current-base-speed-gate.status" >/dev/null ||
    die 'parent diagnostic gate changed'
  grep -Fx 'fail actual=30.26782494070049 floor=30.31067504052998' \
    "$parent_replay_a_out/current-base-strict-a-gate.status" >/dev/null ||
    die 'parent strict-A gate changed'
  grep -Fx 'fail actual=30.27119782672338 floor=30.31067504052998' \
    "$parent_replay_b_out/current-base-strict-b-gate.status" >/dev/null ||
    die 'parent strict-B gate changed'
  jq -e \
    --arg root "$parent_root" --arg vllm "$expected_vllm_head" \
    --arg vllm_tree "$expected_vllm_tree" --arg kernel "$expected_kernel_head" \
    --arg kernel_tree "$expected_kernel_tree" --arg base "$expected_base_digest" \
    --arg image "$expected_both_image_id" --arg receipt "$expected_receipt_sha256" \
    --arg boot "$expected_host_boot_id" --arg host_kernel "$expected_host_kernel" \
    --arg inputs_manifest "$expected_parent_inputs_manifest_sha256" \
    --arg cache_manifest "$expected_parent_cache_manifest_sha256" '
    .schema == "neural-download-current-main-tp1-untreated-control-result-v1" and
    .state == "complete" and .run_root == $root and
    .identity.vllm_head == $vllm and .identity.vllm_tree == $vllm_tree and
    .identity.kernel_head == $kernel and .identity.kernel_tree == $kernel_tree and
    .identity.base_digest == $base and .identity.image_id == $image and
    .identity.receipt_sha256 == $receipt and
    .host.kernel == $host_kernel and .host.boot_id == $boot and
    .floors_tok_s == {diagnostic: 30.2178, strict: 30.31067504052998} and
    .medians_tok_s == {
      diagnostic: 30.27858669748398,
      strict_a: 30.26782494070049,
      strict_b: 30.27119782672338
    } and
    .speed_gates == {diagnostic: true, strict_a: false, strict_b: false} and
    .evidence.frozen_inputs_manifest_sha256 == $inputs_manifest and
    .evidence.compiled_cache_manifest_sha256 == $cache_manifest and
    .evidence.postreboot_hardware_gate_pass == true and
    .evidence.replay_a_full_cache_immutable == true and
    .evidence.replay_b_full_cache_immutable == true and
    .evidence.exact_source_identity_pre_and_post_all_arms == true and
    .evidence.repo_and_host_postflight_pass == true and
    .evidence.model_identity_all_arms == true and
    .evidence.canary_all_arms == true and
    .evidence.realistic_benchmark_all_arms == true and
    .evidence.quality_battery == true and
    .evidence.prompt_order_matches == true and
    .evidence.all_non_speed_gates_pass == true and
    .qualification_ready == false
  ' "$parent_root/control-result.json" >/dev/null ||
    die 'parent aggregate result contract changed'
  jq -e '
    .pass_all == true and .baseline_match_all == true and
    (.exact_cases | length) == 7 and all(.exact_cases[]; .pass == true) and
    (.repeat_case.runs | length) == 8 and .repeat_case.pass == true and
    ([.repeat_case.runs[].sha256] | unique | length) == 1 and
    .long_context_case.pass == true and
    .long_context_case.requested_context_tokens == 8192 and
    .long_context_case.actual_prompt_tokens == 7617 and
    (.baseline_comparisons | length) == 24 and
    all(.baseline_comparisons[]; . == true)
  ' "$parent_replay_a_out/quality.json" >/dev/null ||
    die 'parent quality evidence changed'

  [[ $(sha256sum "$parent_hardware/SHA256SUMS" | awk '{print $1}') == \
     "$expected_parent_hardware_manifest_sha256" &&
     $(sha256sum "$parent_hardware/summary.json" | awk '{print $1}') == \
     "$expected_parent_hardware_summary_sha256" &&
     $(sha256sum "$parent_hardware/final.status" | awk '{print $1}') == \
     "$expected_parent_hardware_status_sha256" ]] ||
    die 'parent hardware-gate identity changed'
  (
    cd "$parent_hardware"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die 'parent hardware-gate evidence changed'
  [[ $(<"$parent_hardware/final.status") == exit_status=0 ]] ||
    die 'parent hardware gate did not pass'
  jq -e --arg boot "$expected_host_boot_id" --arg kernel "$expected_host_kernel" '
    .schema == "neural-download-qwen38-postreboot-hardware-gate-v3" and
    .passed == true and .gate_complete == true and .failure_stage == "complete" and
    .host.boot_id == $boot and .host.kernel == $kernel and
    .host.taint_pre == "0" and .host.taint_post == "0" and
    .gates.four_device_identity == true and .gates.per_card_compute == true and
    .gates.four_device_peer_read == true and
    .gates.four_rank_xccl_allreduce == true and
    .gates.torch_runtime_coherent == true and .gates.root_nvme_health == true and
    .gates.repo_postflight == true and .gates.atomic_lock_handoff == true and
    .gates.selector_and_mask_combined == false and .gates.kernel_reject_events == 0
  ' "$parent_hardware/summary.json" >/dev/null ||
    die 'parent hardware-gate contract changed'

  [[ $(sha256sum "$parent_record" | awk '{print $1}') == \
     "$expected_parent_record_sha256" &&
     $(sha256sum "$parent_closeout" | awk '{print $1}') == \
     "$expected_parent_closeout_sha256" ]] ||
    die 'tracked parent closeout changed'
  jq -e \
    --arg root "$parent_root" --arg campaign "$expected_parent_campaign_manifest_sha256" \
    --arg result "$expected_parent_result_sha256" \
    --arg cache "$expected_parent_cache_manifest_sha256" \
    --arg protected "$expected_protected_values_sha256" '
    .schema == "neural-download-qwen38-current-main-tp1-completed-speed-only-miss-v1" and
    .classification == "complete-speed-only-regression-no-overlay-run" and
    .promotion_allowed == false and .tp2_tp4_authorized == false and
    .decision_compatibility_packet_authorized == true and
    .protected_performance_changed == false and
    .campaign.root == $root and .campaign.campaign_manifest_sha256 == $campaign and
    .campaign.aggregate_result_sha256 == $result and
    .campaign.compiled_cache.manifest_sha256 == $cache and
    .campaign.compiled_cache.files == 1097 and
    .campaign.compiled_cache.best_config_decision_files == 38 and
    .campaign.all_non_speed_gates_pass == true and
    .preservation.complete_protected_performance_ledger_sha256 == $protected and
    .disposition.compiled_cache_transfer_allowed == false and
    .disposition.tp2_tp4_authorized == false
  ' "$parent_record" >/dev/null || die 'tracked parent closeout contract changed'
}

verify_stale_predecessor() {
  local stale_symlink cache_symlink cache_special cache_files cache_best_configs
  local directory_manifest_sha seed_manifest
  for required in "$stale_root/campaign-evidence.sha256" \
      "$stale_root/campaign-evidence.sha256.digest" \
      "$stale_root/inputs/SHA256SUMS" "$stale_root/campaign-failure.json" \
      "$stale_root/final.status" "$stale_fresh_out/final.status" \
      "$stale_fresh_out/decision-overlay-speed-gate.status" \
      "$stale_fresh_out/bench.json" \
      "$stale_fresh_out/cache-manifest.post.sha256" \
      "$stale_fresh_out/cache-manifest.post.sha256.digest" \
      "$stale_fresh_out/cache-directories.post.txt" \
      "$stale_fresh_out/cache-directories.post.sha256" \
      "$stale_hardware/SHA256SUMS" "$stale_hardware/summary.json" \
      "$stale_hardware/final.status"; do
    [[ -f $required ]] || die "sealed r1 predecessor evidence is absent: $required"
  done
  [[ ! -L $stale_root && ! -L $stale_cache && ! -L $stale_hardware ]] ||
    die 'a sealed r1 predecessor root is a symlink'
  stale_symlink=$(find "$stale_root" -path "$stale_cache" -prune -o \
    -type l -print -quit) || die 'r1 predecessor symlink scan failed'
  [[ -z $stale_symlink ]] || die 'r1 predecessor evidence contains a symlink'
  cache_symlink=$(sudo -S -p '' find "$stale_cache" -type l -print -quit \
    <"$sudo_pass_file") || die 'r1 predecessor cache symlink scan failed'
  [[ -z $cache_symlink ]] || die 'r1 predecessor cache contains a symlink'
  cache_special=$(sudo -S -p '' find "$stale_cache" \
    ! -type f ! -type d -print -quit <"$sudo_pass_file") ||
    die 'r1 predecessor cache node-type scan failed'
  [[ -z $cache_special ]] || die 'r1 predecessor cache contains a special node'
  [[ $(findmnt -n -o FSTYPE --target "$stale_cache") == ext4 ]] ||
    die 'r1 predecessor cache is no longer on ext4'

  [[ $(sha256sum "$stale_root/campaign-evidence.sha256" | awk '{print $1}') == \
     "$expected_stale_campaign_manifest_sha256" &&
     $(<"$stale_root/campaign-evidence.sha256.digest") == \
     "$expected_stale_campaign_manifest_sha256" ]] ||
    die 'r1 predecessor campaign manifest changed'
  (
    cd "$stale_root"
    sha256sum -c campaign-evidence.sha256 >/dev/null
  ) || die 'r1 predecessor campaign evidence changed'
  [[ $(sha256sum "$stale_root/inputs/SHA256SUMS" | awk '{print $1}') == \
     "$expected_stale_inputs_manifest_sha256" ]] ||
    die 'r1 predecessor input manifest changed'
  (
    cd "$stale_root/inputs"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die 'r1 predecessor frozen inputs changed'
  [[ $(sha256sum "$stale_root/campaign-failure.json" | awk '{print $1}') == \
     "$expected_stale_failure_sha256" &&
     $(sha256sum "$stale_root/final.status" | awk '{print $1}') == \
     "$expected_stale_final_status_sha256" &&
     $(<"$stale_root/final.status") == 'failed-incomplete mode=all rc=1' ]] ||
    die 'r1 predecessor terminal evidence changed'
  jq -e \
    --arg vllm "$expected_vllm_head" --arg kernel "$expected_kernel_head" \
    --arg base "$expected_base_digest" --arg image "$expected_both_image_id" \
    --arg seed "$expected_seed_manifest_sha256" '
    .schema == "neural-download-current-main-tp1-decision-overlay-failure-v2" and
    .state == "failed-incomplete mode=all rc=1" and .exit_code == 1 and
    .identity.vllm_head == $vllm and .identity.kernel_head == $kernel and
    .identity.base_digest == $base and .identity.image_id == $image and
    .treatment.seed_manifest_sha256 == $seed and
    .arms.fresh.status == "pass" and
    .arms.fresh.median_tok_s == 30.268740193465128 and
    .arms.replay_a.status == "missing" and .arms.replay_a.median_tok_s == null and
    .arms.replay_b.status == "missing" and .arms.replay_b.median_tok_s == null
  ' "$stale_root/campaign-failure.json" >/dev/null ||
    die 'r1 predecessor failure contract changed'

  [[ $(sha256sum "$stale_fresh_out/bench.json" | awk '{print $1}') == \
     "$expected_stale_bench_sha256" &&
     $(<"$stale_fresh_out/final.status") == pass ]] ||
    die 'r1 predecessor diagnostic evidence changed'
  grep -Fqx 'pass actual=30.268740193465128 floor=30.2178' \
    "$stale_fresh_out/decision-overlay-speed-gate.status" ||
    die 'r1 predecessor diagnostic speed gate changed'
  jq -e '
    .summary.tok_s_1_100_intervals_after_ttft.median == 30.268740193465128 and
    .realistic_final_gate.passed == true and
    .fresh_response_validity.cached_tokens_all_zero == true and
    (.rows | length) == 25
  ' "$stale_fresh_out/bench.json" >/dev/null ||
    die 'r1 predecessor diagnostic benchmark contract changed'
  [[ ! -e $stale_root/strict-quality-replay-a &&
     ! -e $stale_root/strict-replay-b &&
     ! -e $stale_root/campaign-result.json ]] ||
    die 'r1 predecessor acquired an unauthorized successor artifact'

  [[ $(sha256sum "$stale_fresh_out/cache-manifest.post.sha256" |
       awk '{print $1}') == "$expected_stale_cache_manifest_sha256" &&
     $(<"$stale_fresh_out/cache-manifest.post.sha256.digest") == \
       "$expected_stale_cache_manifest_sha256" &&
     $(sha256sum "$stale_fresh_out/cache-directories.post.txt" |
       awk '{print $1}') == "$expected_stale_directory_manifest_sha256" &&
     $(<"$stale_fresh_out/cache-directories.post.sha256") == \
       "$expected_stale_directory_manifest_sha256" ]] ||
    die 'r1 predecessor cache evidence changed'
  cache_files=$(sudo -S -p '' find "$stale_cache" -type f \
    <"$sudo_pass_file" | wc -l)
  cache_best_configs=$(sudo -S -p '' find "$stale_cache" -type f \
    -name '*.best_config' <"$sudo_pass_file" | wc -l)
  [[ $cache_files == 497 && $cache_best_configs == 38 ]] ||
    die 'r1 predecessor cache file counts changed'
  sudo -S -p '' bash -c '
    set -euo pipefail
    cd "$1"
    sha256sum -c "$2" >/dev/null
  ' bash "$stale_cache" "$stale_fresh_out/cache-manifest.post.sha256" \
    <"$sudo_pass_file" || die 'actual r1 predecessor cache bytes changed'
  directory_manifest_sha=$(
    sudo -S -p '' bash -c '
      set -euo pipefail
      cd "$1"
      find . -type d -printf "%P\n" | LC_ALL=C sort
    ' bash "$stale_cache" <"$sudo_pass_file" | sha256sum | awk '{print $1}'
  )
  [[ $directory_manifest_sha == "$expected_stale_directory_manifest_sha256" ]] ||
    die 'actual r1 predecessor cache directory set changed'
  for seed_manifest in "$stale_fresh_out/best-config-seed.source.sha256" \
      "$stale_fresh_out/best-config-seed.precompile.sha256" \
      "$stale_fresh_out/best-config-seed.postcompile.sha256" \
      "$stale_fresh_out/best-config-seed.final.sha256" \
      "$stale_fresh_out/best-config-seed.postshutdown.sha256"; do
    [[ $(sha256sum "$seed_manifest" | awk '{print $1}') == \
       "$expected_seed_manifest_sha256" ]] ||
      die "r1 predecessor decision evidence changed: $seed_manifest"
  done

  [[ $(sha256sum "$stale_hardware/SHA256SUMS" | awk '{print $1}') == \
     "$expected_stale_hardware_manifest_sha256" &&
     $(sha256sum "$stale_hardware/summary.json" | awk '{print $1}') == \
     "$expected_stale_hardware_summary_sha256" &&
     $(<"$stale_hardware/final.status") == exit_status=0 ]] ||
    die 'r1 predecessor hardware evidence changed'
  (
    cd "$stale_hardware"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die 'r1 predecessor hardware manifest failed'

  [[ $(sha256sum "$stale_root/inputs/qualification-runner.sh" |
       awk '{print $1}') == "$expected_stale_wrapper_sha256" &&
     $(sha256sum "$stale_root/inputs/preregistration.md" |
       awk '{print $1}') == "$expected_stale_prereg_sha256" &&
     $(sha256sum "$stale_record" | awk '{print $1}') == \
       "$expected_stale_record_sha256" &&
     $(sha256sum "$stale_closeout" | awk '{print $1}') == \
       "$expected_stale_closeout_sha256" ]] ||
    die 'tracked or frozen r1 predecessor closeout changed'
  jq -e \
    --arg root "$stale_root" --arg campaign "$expected_stale_campaign_manifest_sha256" \
    --arg inputs "$expected_stale_inputs_manifest_sha256" \
    --arg cache "$expected_stale_cache_manifest_sha256" \
    --arg dirs "$expected_stale_directory_manifest_sha256" '
    .classification == "failed-incomplete-live-lab-origin-main-advanced-after-seeded-fresh-diagnostic" and
    .candidate_qualification == "incomplete-nonpromotable" and
    .promotion_allowed == false and .tp2_tp4_authorized == false and
    .protected_performance_changed == false and
    .campaign.root == $root and .campaign.manifest_sha256 == $campaign and
    .campaign.inputs_manifest_sha256 == $inputs and
    .campaign.compiled_cache.file_manifest_sha256 == $cache and
    .campaign.compiled_cache.directory_manifest_sha256 == $dirs and
    .campaign.arms.seeded_fresh_diagnostic.speed_gate == "pass" and
    .campaign.arms.seeded_fresh_diagnostic.quality_battery_executed == false and
    .campaign.arms.strict_quality_replay_a.status == "missing" and
    .campaign.arms.strict_replay_b.status == "missing" and
    (.disposition.r1_roots | startswith("closed and checksum-sealed"))
  ' "$stale_record" >/dev/null || die 'tracked r1 predecessor contract changed'
}

verify_build_receipt() {
  local archive_dir
  local -a archived_vllm_wheels
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
  ' "$receipt" >/dev/null || die 'exact 6a9c build receipt contract changed'
  archive_dir=$(jq -r .external_archive "$receipt")
  [[ $archive_dir == \
    /mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T185928Z-6a9c69fa85-baaa05bb4e &&
    -d $archive_dir ]] || die 'exact 6a9c external build archive is absent'
  (
    cd "$archive_dir"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die '6a9c external build archive checksum failure'
  cmp -s "$receipt" "$archive_dir/build-receipt.json" ||
    die 'tracked and archived 6a9c receipts differ'
  mapfile -t archived_vllm_wheels < <(
    find "$archive_dir" -maxdepth 1 -type f -name 'vllm-*.whl' -print
  )
  [[ ${#archived_vllm_wheels[@]} -eq 1 ]] ||
    die '6a9c archive must contain exactly one vLLM wheel'
  unzip -Z1 "${archived_vllm_wheels[0]}" |
    grep -Fx 'vllm/model_executor/layers/batch_invariant_configs.py' >/dev/null ||
    die '6a9c tuned-config module is missing from the archived wheel'
}

validate_hardware_gate() {
  for required in "$hardware_gate/summary.json" "$hardware_gate/final.status" \
      "$hardware_gate/SHA256SUMS"; do
    [[ -f $required ]] || die "missing fresh hardware-gate evidence: $required"
  done
  (
    cd "$hardware_gate"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die 'fresh hardware-gate evidence changed'
  [[ $(<"$hardware_gate/final.status") == exit_status=0 ]] ||
    die 'fresh hardware gate did not exit cleanly'
  jq -e \
    --arg boot_id "$expected_host_boot_id" --arg kernel "$expected_host_kernel" \
    --arg repo_head "$(git -C "$repo" rev-parse HEAD)" '
    .schema == "neural-download-qwen38-postreboot-hardware-gate-v3" and
    .passed == true and .gate_complete == true and .failure_stage == "complete" and
    .host.boot_id == $boot_id and .host.kernel == $kernel and
    .host.taint_pre == "0" and .host.taint_post == "0" and
    .repo_head == $repo_head and .gates.four_device_identity == true and
    .gates.per_card_compute == true and .gates.four_device_peer_read == true and
    .gates.four_rank_xccl_allreduce == true and .gates.repo_postflight == true and
    .gates.atomic_lock_handoff == true and .gates.torch_runtime_coherent == true and
    .gates.root_nvme_health == true and
    .gates.selector_and_mask_combined == false and .gates.kernel_reject_events == 0 and
    (.gates.known_corrected_root_nvme_events == 0 or
      .gates.known_corrected_root_nvme_events == 1)
  ' "$hardware_gate/summary.json" >/dev/null ||
    die 'fresh hardware gate is invalid for this commit and boot'
}

prepare_inputs() {
  local seed_file relative
  [[ ! -e $result_root ]] || die "result root already exists: $result_root"
  mkdir -p -- "$inputs/decision-seed"
  cp --reflink=never -- "$runner" "$inputs/strict-smoke.sh"
  cp --reflink=never -- "$script_path" "$inputs/qualification-runner.sh"
  cp --reflink=never -- "$receipt" "$inputs/build-receipt.json"
  cp --reflink=never -- "$suite" "$inputs/validation-suite.json"
  cp --reflink=never -- "$baseline" "$inputs/quality-baseline.json"
  cp --reflink=never -- "$model_manifest" "$inputs/model-manifest.json"
  cp --reflink=never -- "$model_verifier" "$inputs/verify-model-direct.py"
  cp --reflink=never -- "$bench_helper" "$inputs/bench-openai-realistic-suite.py"
  cp --reflink=never -- "$quality_helper" "$inputs/qwen38-text-quality-suite.py"
  cp --reflink=never -- "$kernel_delta_classifier" \
    "$inputs/kernel-delta-classifier.py"
  cp --reflink=never -- "$kernel_delta_classifier_test" \
    "$inputs/kernel-delta-classifier-test.py"
  printf '%s\n' "$classifier_test_receipt" \
    >"$inputs/kernel-delta-classifier-test.receipt.txt"
  cp --reflink=never -- "$hardware_gate_runner" \
    "$inputs/hardware-gate-runner.sh"
  cp --reflink=never -- "$prereg" "$inputs/preregistration.md"
  cp --reflink=never -- "$overlay_manifest" \
    "$inputs/decision-seed-manifest.sha256"
  cp --reflink=never -- "$overlay_metadata" \
    "$inputs/decision-overlay-metadata.json"
  cp --reflink=never -- "$overlay_readme" \
    "$inputs/decision-overlay-README.md"
  cp --reflink=never -- "$overlay_census" \
    "$inputs/decision-overlay-compatibility-census.tsv"
  while IFS= read -r -d '' seed_file; do
    relative=${seed_file#"$seed_source"/}
    mkdir -p -- "$inputs/decision-seed/$(dirname -- "$relative")"
    cp --reflink=never -- "$seed_file" "$inputs/decision-seed/$relative"
  done < <(find "$seed_source" -type f -name '*.best_config' -print0 |
    LC_ALL=C sort -z)

  cp --reflink=never -- "$parent_record" "$inputs/parent-closeout.json"
  cp --reflink=never -- "$parent_closeout" "$inputs/parent-closeout.md"
  cp --reflink=never -- "$parent_root/control-result.json" \
    "$inputs/parent-control-result.json"
  cp --reflink=never -- "$parent_root/control-result.sha256" \
    "$inputs/parent-control-result.sha256"
  cp --reflink=never -- "$parent_root/campaign-evidence.sha256" \
    "$inputs/parent-campaign-evidence.sha256"
  cp --reflink=never -- "$parent_root/campaign-evidence.sha256.digest" \
    "$inputs/parent-campaign-evidence.sha256.digest"
  cp --reflink=never -- "$parent_root/inputs/SHA256SUMS" \
    "$inputs/parent-inputs-SHA256SUMS"
  cp --reflink=never -- "$parent_fresh_out/cache-manifest.post.sha256" \
    "$inputs/parent-cache-manifest.sha256"
  cp --reflink=never -- "$parent_root/final.status" \
    "$inputs/parent-final.status"
  cp --reflink=never -- "$stale_record" \
    "$inputs/predecessor-closeout.json"
  cp --reflink=never -- "$stale_closeout" \
    "$inputs/predecessor-closeout.md"
  cp --reflink=never -- "$stale_root/campaign-evidence.sha256" \
    "$inputs/predecessor-campaign-evidence.sha256"
  cp --reflink=never -- "$stale_root/campaign-evidence.sha256.digest" \
    "$inputs/predecessor-campaign-evidence.sha256.digest"
  cp --reflink=never -- "$stale_root/inputs/SHA256SUMS" \
    "$inputs/predecessor-inputs-SHA256SUMS"
  cp --reflink=never -- "$stale_root/campaign-failure.json" \
    "$inputs/predecessor-campaign-failure.json"
  cp --reflink=never -- "$stale_root/final.status" \
    "$inputs/predecessor-final.status"
  cp --reflink=never -- "$stale_fresh_out/bench.json" \
    "$inputs/predecessor-diagnostic-bench.json"
  cp --reflink=never -- "$stale_fresh_out/decision-overlay-speed-gate.status" \
    "$inputs/predecessor-diagnostic-speed-gate.status"
  cp --reflink=never -- "$stale_fresh_out/cache-manifest.post.sha256" \
    "$inputs/predecessor-cache-manifest.sha256"
  cp --reflink=never -- "$stale_fresh_out/cache-directories.post.txt" \
    "$inputs/predecessor-cache-directories.txt"
  cp --reflink=never -- "$stale_hardware/SHA256SUMS" \
    "$inputs/predecessor-hardware-SHA256SUMS"
  cp --reflink=never -- "$stale_hardware/summary.json" \
    "$inputs/predecessor-hardware-summary.json"
  cp --reflink=never -- "$stale_hardware/final.status" \
    "$inputs/predecessor-hardware-final.status"
  cp --reflink=never -- "$protected_manifest" \
    "$inputs/protected-overlay-manifest.json"
  cp --reflink=never -- "$tp2_overlay/manifest.sha256" \
    "$inputs/protected-tp2-decision-manifest.sha256"
  cp --reflink=never -- "$tp4_overlay/manifest.sha256" \
    "$inputs/protected-tp4-decision-manifest.sha256"

  cp --reflink=never -- "$hardware_gate/summary.json" \
    "$inputs/current-hardware-gate-summary.json"
  cp --reflink=never -- "$hardware_gate/final.status" \
    "$inputs/current-hardware-gate-final.status"
  cp --reflink=never -- "$hardware_gate/SHA256SUMS" \
    "$inputs/current-hardware-gate-SHA256SUMS"
  git -C "$repo" rev-parse HEAD >"$inputs/lab-head.txt"
  uname -r >"$inputs/host-kernel-release.txt"
  uname -a >"$inputs/host-uname.txt"
  cp --reflink=never -- /proc/sys/kernel/random/boot_id \
    "$inputs/host-boot-id.txt"
  cp --reflink=never -- /proc/cmdline "$inputs/host-cmdline.txt"
  (
    cd "$inputs"
    find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z |
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
  local executable_inputs frozen_lab_head live_vllm_head
  local live_kernel_head live_base_digest writable_input writable_input_dir
  local input_symlink
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
  [[ -z $input_symlink ]] || die 'frozen inputs contain a symlink'
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
  [[ $(sha256sum "$inputs/build-receipt.json" | awk '{print $1}') == \
     "$expected_receipt_sha256" &&
     $(sha256sum "$inputs/validation-suite.json" | awk '{print $1}') == \
     "$expected_suite_sha256" &&
     $(sha256sum "$inputs/quality-baseline.json" | awk '{print $1}') == \
     "$expected_baseline_sha256" &&
     $(sha256sum "$inputs/preregistration.md" | awk '{print $1}') == \
     "$expected_prereg_sha256" &&
     $(sha256sum "$inputs/decision-overlay-metadata.json" | awk '{print $1}') == \
     "$expected_overlay_metadata_sha256" &&
     $(sha256sum "$inputs/decision-overlay-compatibility-census.tsv" |
       awk '{print $1}') == "$expected_overlay_census_sha256" ]] ||
    die 'a frozen record-grade input is not exact'
  [[ $(sha256sum "$inputs/decision-seed-manifest.sha256" | awk '{print $1}') == \
     "$expected_seed_manifest_sha256" ]] || die 'frozen seed manifest changed'
  [[ $(find "$inputs/decision-seed" -type f | wc -l) == \
     "$expected_seed_count" &&
     $(find "$inputs/decision-seed" -type f -name '*.best_config' | wc -l) == \
     "$expected_seed_count" ]] || die 'frozen seed file set changed'
  (
    cd "$inputs/decision-seed"
    sha256sum -c ../decision-seed-manifest.sha256 >/dev/null
  ) || die 'frozen decision bytes changed'
  [[ $(sha256sum "$inputs/parent-control-result.json" | awk '{print $1}') == \
     "$expected_parent_result_sha256" &&
     $(<"$inputs/parent-control-result.sha256") == \
     "$expected_parent_result_sha256" &&
     $(sha256sum "$inputs/parent-campaign-evidence.sha256" | awk '{print $1}') == \
     "$expected_parent_campaign_manifest_sha256" &&
     $(<"$inputs/parent-campaign-evidence.sha256.digest") == \
     "$expected_parent_campaign_manifest_sha256" &&
     $(sha256sum "$inputs/parent-inputs-SHA256SUMS" | awk '{print $1}') == \
     "$expected_parent_inputs_manifest_sha256" &&
     $(sha256sum "$inputs/parent-cache-manifest.sha256" | awk '{print $1}') == \
     "$expected_parent_cache_manifest_sha256" &&
     $(<"$inputs/parent-final.status") == \
     complete-speed-only-regression-no-overlay-run ]] ||
    die 'frozen parent prerequisite changed'
  [[ $(sha256sum "$inputs/predecessor-closeout.json" | awk '{print $1}') == \
       "$expected_stale_record_sha256" &&
     $(sha256sum "$inputs/predecessor-closeout.md" | awk '{print $1}') == \
       "$expected_stale_closeout_sha256" &&
     $(sha256sum "$inputs/predecessor-campaign-evidence.sha256" |
       awk '{print $1}') == "$expected_stale_campaign_manifest_sha256" &&
     $(<"$inputs/predecessor-campaign-evidence.sha256.digest") == \
       "$expected_stale_campaign_manifest_sha256" &&
     $(sha256sum "$inputs/predecessor-inputs-SHA256SUMS" | awk '{print $1}') == \
       "$expected_stale_inputs_manifest_sha256" &&
     $(sha256sum "$inputs/predecessor-campaign-failure.json" |
       awk '{print $1}') == "$expected_stale_failure_sha256" &&
     $(sha256sum "$inputs/predecessor-final.status" | awk '{print $1}') == \
       "$expected_stale_final_status_sha256" &&
     $(<"$inputs/predecessor-final.status") == \
       'failed-incomplete mode=all rc=1' &&
     $(sha256sum "$inputs/predecessor-diagnostic-bench.json" |
       awk '{print $1}') == "$expected_stale_bench_sha256" &&
     $(<"$inputs/predecessor-diagnostic-speed-gate.status") == \
       'pass actual=30.268740193465128 floor=30.2178' &&
     $(sha256sum "$inputs/predecessor-cache-manifest.sha256" |
       awk '{print $1}') == "$expected_stale_cache_manifest_sha256" &&
     $(sha256sum "$inputs/predecessor-cache-directories.txt" |
       awk '{print $1}') == "$expected_stale_directory_manifest_sha256" &&
     $(sha256sum "$inputs/predecessor-hardware-SHA256SUMS" |
       awk '{print $1}') == "$expected_stale_hardware_manifest_sha256" &&
     $(sha256sum "$inputs/predecessor-hardware-summary.json" |
       awk '{print $1}') == "$expected_stale_hardware_summary_sha256" &&
     $(<"$inputs/predecessor-hardware-final.status") == exit_status=0 ]] ||
    die 'frozen r1 predecessor prerequisite changed'

  [[ $(<"$inputs/host-kernel-release.txt") == "$expected_host_kernel" &&
     $(uname -r) == "$expected_host_kernel" ]] ||
    die 'host kernel changed during overlay qualification'
  uname -a | cmp -s - "$inputs/host-uname.txt" ||
    die 'host uname changed during overlay qualification'
  cmp -- /proc/sys/kernel/random/boot_id "$inputs/host-boot-id.txt" >/dev/null ||
    die 'host rebooted during overlay qualification'
  [[ $(<"$inputs/host-boot-id.txt") == "$expected_host_boot_id" ]] ||
    die 'frozen host boot is not the preregistered boot'
  cmp -- /proc/cmdline "$inputs/host-cmdline.txt" >/dev/null ||
    die 'host command line changed during overlay qualification'
  cmp -s "$hardware_gate/SHA256SUMS" \
    "$inputs/current-hardware-gate-SHA256SUMS" ||
    die 'fresh hardware-gate manifest changed during overlay qualification'
  (
    cd "$hardware_gate"
    sha256sum -c "$inputs/current-hardware-gate-SHA256SUMS" >/dev/null
  ) || die 'fresh hardware-gate evidence changed during overlay qualification'
  cmp -s "$hardware_gate/summary.json" \
    "$inputs/current-hardware-gate-summary.json" ||
    die 'fresh hardware-gate summary changed during overlay qualification'
  cmp -s "$hardware_gate/final.status" \
    "$inputs/current-hardware-gate-final.status" ||
    die 'fresh hardware-gate status changed during overlay qualification'
  validate_hardware_gate
  verify_parent_campaign
  verify_decision_bundle
  verify_protected_values

  [[ -z $(git -C "$repo" status --porcelain=v1 --untracked-files=all) ]] ||
    die 'lab repository became dirty during overlay qualification'
  [[ $(git -C "$repo" branch --show-current) == main ]] ||
    die 'lab repository left main during overlay qualification'
  frozen_lab_head=$(<"$inputs/lab-head.txt")
  [[ $(git -C "$repo" rev-parse HEAD) == "$frozen_lab_head" ]] ||
    die 'local lab commit changed during overlay qualification'
  live_vllm_head=$(timeout --signal=TERM --kill-after=5s 30s \
    git ls-remote --exit-code https://github.com/vllm-project/vllm.git \
    refs/heads/main | awk 'NR == 1 {print $1}')
  [[ $live_vllm_head == "$expected_vllm_head" ]] ||
    die 'vLLM main advanced during overlay qualification'
  live_kernel_head=$(timeout --signal=TERM --kill-after=5s 30s \
    git ls-remote --exit-code https://github.com/vllm-project/vllm-xpu-kernels.git \
    refs/heads/main | awk 'NR == 1 {print $1}')
  [[ $live_kernel_head == "$expected_kernel_head" ]] ||
    die 'XPU-kernel main advanced during overlay qualification'
  live_base_digest=$(timeout --signal=TERM --kill-after=5s 60s \
    sudo -S -p '' docker buildx imagetools inspect \
    vllm/vllm-openai-xpu:nightly --format '{{.Manifest.Digest}}' \
    <"$sudo_pass_file")
  [[ $live_base_digest == "$expected_base_digest" ]] ||
    die 'official nightly advanced during overlay qualification'
  [[ $(sudo -S -p '' docker image inspect "$expected_both_image_id" \
      --format '{{.Id}}' <"$sudo_pass_file") == "$expected_both_image_id" ]] ||
     die 'exact both-current image is absent or changed'
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
  local state=$1 status_tmp="$result_root/.final.status.tmp.$$"
  printf '%s\n' "$state" >"$status_tmp"
  mv -f -- "$status_tmp" "$result_root/final.status"
}

write_campaign_evidence() {
  local manifest_tmp="$result_root/.campaign-evidence.sha256.tmp.$$"
  local digest_tmp="$result_root/.campaign-evidence.sha256.digest.tmp.$$"
  local symlink_output
  symlink_output=$(
    cd "$result_root"
    find . -path './overlay-cache' -prune -o -type l -print
  ) || return 1
  [[ -z $symlink_output ]] || {
    printf 'refusing to seal symlinked campaign evidence:\n%s\n' \
      "$symlink_output" >&2
    return 1
  }
  (
    cd "$result_root"
    find . -path './overlay-cache' -prune -o -type f \
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
      --arg fresh_status "$(read_status_or_missing "$fresh_out/final.status")" \
      --arg replay_a_status "$(read_status_or_missing "$replay_a_out/final.status")" \
      --arg replay_b_status "$(read_status_or_missing "$replay_b_out/final.status")" \
      --argjson diagnostic_median "$(read_median_or_null "$fresh_out/bench.json")" \
      --argjson strict_a_median "$(read_median_or_null "$replay_a_out/bench.json")" \
      --argjson strict_b_median "$(read_median_or_null "$replay_b_out/bench.json")" \
      --arg vllm_head "$expected_vllm_head" \
      --arg kernel_head "$expected_kernel_head" \
      --arg base_digest "$expected_base_digest" \
      --arg image_id "$expected_both_image_id" \
      --arg receipt_sha256 "$expected_receipt_sha256" \
      --arg parent_result_sha256 "$expected_parent_result_sha256" \
      --arg parent_campaign_manifest_sha256 \
        "$expected_parent_campaign_manifest_sha256" \
      --arg seed_manifest_sha256 "$expected_seed_manifest_sha256" '{
        schema: "neural-download-current-main-tp1-decision-overlay-failure-v2",
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
        parent: {
          aggregate_result_sha256: $parent_result_sha256,
          campaign_manifest_sha256: $parent_campaign_manifest_sha256
        },
        treatment: {seed_manifest_sha256: $seed_manifest_sha256},
        arms: {
          fresh: {status: $fresh_status, median_tok_s: $diagnostic_median},
          replay_a: {status: $replay_a_status, median_tok_s: $strict_a_median},
          replay_b: {status: $replay_b_status, median_tok_s: $strict_b_median}
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
    -u BEST_CONFIG_SEED_DIR -u EXPECTED_BEST_CONFIG_SEED_COUNT \
    -u EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256 \
    -u BEST_CONFIG_TARGET_AOT_NAMESPACE \
    -u EXPECTED_CACHE_OUTER_NAMESPACE -u EXPECTED_CACHE_CODE_HASH \
    -u EXPECTED_CACHE_COMPILER_HASH -u EXPECTED_CACHE_CONFIG_HASH \
    -u EXPECTED_CACHE_ENV_SHA256 -u EXPECTED_COMPUTATION_GRAPH_SHA256S \
    "$@"
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

validate_arm_common() {
  local arm_out=$1
  [[ $(<"$arm_out/final.status") == pass ]] ||
    die "model arm did not pass non-speed gates: $arm_out"
  jq -e '
    .status == "verified" and (.files | length) == 19 and
    all(.files[]; .ok == true)
  ' "$arm_out/model-direct-and-ordinary-verify.json" >/dev/null ||
    die "model identity gate changed: $arm_out"
  jq -e '.content == "14" and .cached_tokens == 0' \
    "$arm_out/canary.json" >/dev/null || die "canary gate changed: $arm_out"
  jq -e '
    .realistic_final_gate.passed == true and
    .fresh_response_validity.cached_tokens_all_zero == true and
    (.rows | length) == 25
  ' "$arm_out/bench.json" >/dev/null || die "benchmark gate changed: $arm_out"
  [[ $(<"$arm_out/upstream-vllm.pre.txt") == "$expected_vllm_head" &&
     $(<"$arm_out/upstream-vllm.post.txt") == "$expected_vllm_head" &&
     $(<"$arm_out/upstream-kernel.pre.txt") == "$expected_kernel_head" &&
     $(<"$arm_out/upstream-kernel.post.txt") == "$expected_kernel_head" &&
     $(<"$arm_out/upstream-nightly-base.pre.txt") == "$expected_base_digest" &&
     $(<"$arm_out/upstream-nightly-base.post.txt") == "$expected_base_digest" ]] ||
    die "arm source identity changed: $arm_out"
}

validate_quality_arm() {
  validate_arm_common "$replay_a_out"
  jq -e '
    .pass_all == true and .baseline_match_all == true and
    (.exact_cases | length) == 7 and all(.exact_cases[]; .pass == true) and
    (.repeat_case.runs | length) == 8 and .repeat_case.pass == true and
    ([.repeat_case.runs[].sha256] | unique | length) == 1 and
    .long_context_case.pass == true and
    .long_context_case.requested_context_tokens == 8192 and
    .long_context_case.actual_prompt_tokens == 7617 and
    .long_context_case.usage.prompt_tokens_details.cached_tokens == 0 and
    (.baseline_comparisons | length) == 24 and
    all(.baseline_comparisons[]; . == true)
  ' "$replay_a_out/quality.json" >/dev/null ||
    die 'overlay strict-A quality battery changed'
}

freeze_overlay_cache_directories() {
  local directory_manifest_tmp="$fresh_out/.cache-directories.post.txt.tmp.$$"
  local directory_digest_tmp="$fresh_out/.cache-directories.post.sha256.tmp.$$"
  sudo -S -p '' bash -c '
    set -euo pipefail
    cd "$1"
    find . -type d -printf "%P\n" | LC_ALL=C sort
  ' bash "$overlay_cache" <"$sudo_pass_file" >"$directory_manifest_tmp" ||
    die 'could not freeze the fresh cache directory set'
  mv -f -- "$directory_manifest_tmp" \
    "$fresh_out/cache-directories.post.txt"
  sha256sum "$fresh_out/cache-directories.post.txt" | awk '{print $1}' \
    >"$directory_digest_tmp"
  mv -f -- "$directory_digest_tmp" \
    "$fresh_out/cache-directories.post.sha256"
  frozen_overlay_directory_manifest_sha256=$(
    <"$fresh_out/cache-directories.post.sha256"
  )
  [[ $frozen_overlay_directory_manifest_sha256 =~ ^[0-9a-f]{64}$ ]] ||
    die 'could not freeze the cache-directory manifest digest'
}

validate_overlay_cache_tree() {
  local cache_real symlink_output special_output actual_file_count
  local expected_file_count actual_directory_manifest_sha256
  [[ -d $overlay_cache && ! -L $overlay_cache ]] ||
    die 'overlay cache root is not a real directory'
  cache_real=$(realpath -e -- "$overlay_cache")
  [[ $cache_real == "$overlay_cache" ]] ||
    die 'overlay cache root is not the frozen canonical path'
  [[ $(findmnt -n -o FSTYPE --target "$overlay_cache") == ext4 ]] ||
    die 'overlay cache is not on ext4'
  symlink_output=$(sudo -S -p '' find "$overlay_cache" -type l -print -quit \
    <"$sudo_pass_file") || die 'overlay cache symlink scan failed'
  [[ -z $symlink_output ]] ||
    die "overlay cache contains a symlink: $symlink_output"
  special_output=$(sudo -S -p '' find "$overlay_cache" \
    ! -type f ! -type d -print -quit <"$sudo_pass_file") ||
    die 'overlay cache node-type scan failed'
  [[ -z $special_output ]] ||
    die "overlay cache contains a special node: $special_output"
  expected_file_count=$(wc -l <"$fresh_out/cache-manifest.post.sha256")
  actual_file_count=$(sudo -S -p '' find "$overlay_cache" -type f \
    <"$sudo_pass_file" | wc -l)
  [[ $actual_file_count == "$expected_file_count" ]] ||
    die 'overlay cache regular-file count changed'
  [[ $frozen_overlay_directory_manifest_sha256 =~ ^[0-9a-f]{64}$ &&
     $(sha256sum "$fresh_out/cache-directories.post.txt" | awk '{print $1}') == \
     "$frozen_overlay_directory_manifest_sha256" &&
     $(<"$fresh_out/cache-directories.post.sha256") == \
     "$frozen_overlay_directory_manifest_sha256" ]] ||
    die 'frozen overlay cache directory manifest changed'
  actual_directory_manifest_sha256=$(
    sudo -S -p '' bash -c '
      set -euo pipefail
      cd "$1"
      find . -type d -printf "%P\n" | LC_ALL=C sort
    ' bash "$overlay_cache" <"$sudo_pass_file" | sha256sum | awk '{print $1}'
  )
  [[ $actual_directory_manifest_sha256 == \
     "$frozen_overlay_directory_manifest_sha256" ]] ||
    die 'overlay cache directory set changed'
}

validate_fresh_overlay_cache() {
  local cache_best_configs seed_manifest
  validate_arm_common "$fresh_out"
  [[ $frozen_overlay_cache_manifest_sha256 =~ ^[0-9a-f]{64}$ ]] ||
    die 'original overlay cache-manifest digest is absent'
  [[ $(<"$fresh_out/cache-manifest.post.sha256.digest") == \
     "$frozen_overlay_cache_manifest_sha256" &&
     $(sha256sum "$fresh_out/cache-manifest.post.sha256" | awk '{print $1}') == \
     "$frozen_overlay_cache_manifest_sha256" ]] ||
    die 'fresh overlay cache manifest changed'
  validate_overlay_cache_tree
  for seed_manifest in "$fresh_out/best-config-seed.source.sha256" \
      "$fresh_out/best-config-seed.precompile.sha256" \
      "$fresh_out/best-config-seed.postcompile.sha256" \
      "$fresh_out/best-config-seed.final.sha256" \
      "$fresh_out/best-config-seed.postshutdown.sha256"; do
    [[ $(sha256sum "$seed_manifest" | awk '{print $1}') == \
       "$expected_seed_manifest_sha256" ]] ||
      die "seed decision evidence changed: $seed_manifest"
    cmp -s "$fresh_out/best-config-seed.source.sha256" "$seed_manifest" ||
      die 'seed decision bytes changed during fresh compilation or workload'
  done
  cache_best_configs=$(sudo -S -p '' find "$overlay_cache" -type f \
    -name '*.best_config' <"$sudo_pass_file" | wc -l)
  [[ $cache_best_configs == "$expected_seed_count" ]] ||
    die 'overlay cache contains extra best_config records'
  sudo -S -p '' bash -c '
    set -euo pipefail
    cd "$1"
    sha256sum -c "$2" >/dev/null
  ' bash "$overlay_cache" "$fresh_out/cache-manifest.post.sha256" \
    <"$sudo_pass_file" || die 'actual fresh overlay cache bytes changed'
}

require_overlay_fresh() {
  verify_inputs
  validate_fresh_overlay_cache
  grep -q '^pass ' "$fresh_out/decision-overlay-speed-gate.status" ||
    die 'seeded-fresh diagnostic speed gate did not pass'
}

require_overlay_replay_a() {
  require_overlay_fresh
  validate_quality_arm
  grep -q '^pass ' "$replay_a_out/decision-overlay-strict-a-gate.status" ||
    die 'overlay strict replay A speed gate did not pass'
  [[ $(sha256sum "$replay_a_out/cache-manifest.pre.sha256" |
       awk '{print $1}') == "$frozen_overlay_cache_manifest_sha256" &&
     $(sha256sum "$replay_a_out/cache-manifest.post.sha256" |
       awk '{print $1}') == "$frozen_overlay_cache_manifest_sha256" ]] ||
    die 'overlay replay-A cache evidence diverges from fresh cache'
  cmp -s "$replay_a_out/cache-manifest.pre.sha256" \
    "$replay_a_out/cache-manifest.post.sha256" ||
    die 'overlay replay A changed the complete cache'
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
  failure_tmp="$result_root/.overlay-non-speed-failure.json.tmp.$$"
  jq -n \
    --arg arm "$arm_name" --argjson arm_exit_code "$arm_rc" \
    --arg reason "$(<"$arm_out/qualification-failure.reason.txt")" \
    --arg arm_status "$arm_status" --arg vllm_head "$expected_vllm_head" \
    --arg kernel_head "$expected_kernel_head" \
    --arg base_digest "$expected_base_digest" \
    --arg image_id "$expected_both_image_id" \
    --arg boot_id "$expected_host_boot_id" \
    --arg parent_result_sha256 "$expected_parent_result_sha256" \
    --arg seed_manifest_sha256 "$expected_seed_manifest_sha256" '{
      schema: "neural-download-current-main-tp1-decision-overlay-non-speed-failure-v1",
      state: "overlay-non-speed-failure",
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
      },
      parent_result_sha256: $parent_result_sha256,
      seed_manifest_sha256: $seed_manifest_sha256
    }' >"$failure_tmp"
  mv -f -- "$failure_tmp" "$result_root/overlay-non-speed-failure.json"
  seal_campaign_status 'overlay-non-speed-failure'
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

close_speed_only_miss() {
  local terminal_state=$1 failed_arm=$2 actual=$3 floor=$4
  local completed_arms result_tmp classification
  local quality_battery_executed quality_battery_pass
  verify_inputs
  validate_fresh_overlay_cache
  case $failed_arm in
    seeded-fresh-diagnostic)
      grep -Fqx "fail actual=$actual floor=$floor" \
        "$fresh_out/decision-overlay-speed-gate.status" ||
        die 'diagnostic negative closure lacks a failed speed gate'
      completed_arms=1
      classification=complete-non-speed-clean-speed-only-miss
      quality_battery_executed=false
      quality_battery_pass=null
      ;;
    strict-quality-replay-a)
      grep -q '^pass ' "$fresh_out/decision-overlay-speed-gate.status" ||
        die 'strict-A negative closure lacks a passed diagnostic gate'
      validate_quality_arm
      [[ $(sha256sum "$replay_a_out/cache-manifest.pre.sha256" |
           awk '{print $1}') == "$frozen_overlay_cache_manifest_sha256" &&
         $(sha256sum "$replay_a_out/cache-manifest.post.sha256" |
           awk '{print $1}') == "$frozen_overlay_cache_manifest_sha256" ]] ||
        die 'strict-A negative closure lacks immutable cache evidence'
      cmp -s "$replay_a_out/cache-manifest.pre.sha256" \
        "$replay_a_out/cache-manifest.post.sha256" ||
        die 'strict-A negative closure cache changed'
      grep -Fqx "fail actual=$actual floor=$floor" \
        "$replay_a_out/decision-overlay-strict-a-gate.status" ||
        die 'strict-A negative closure lacks a failed speed gate'
      completed_arms=2
      classification=complete-quality-clean-speed-only-miss
      quality_battery_executed=true
      quality_battery_pass=true
      ;;
    *) die "unsupported speed-only terminal arm: $failed_arm" ;;
  esac
  result_tmp="$result_root/.campaign-result.json.tmp.$$"
  jq -n \
    --arg run_root "$result_root" --arg state "$terminal_state" \
    --arg classification "$classification" \
    --arg failed_arm "$failed_arm" --argjson completed_arms "$completed_arms" \
    --argjson quality_battery_executed "$quality_battery_executed" \
    --argjson quality_battery_pass "$quality_battery_pass" \
    --argjson failed_actual "$actual" --argjson failed_floor "$floor" \
    --arg vllm_head "$expected_vllm_head" --arg vllm_tree "$expected_vllm_tree" \
    --arg kernel_head "$expected_kernel_head" --arg kernel_tree "$expected_kernel_tree" \
    --arg base_digest "$expected_base_digest" --arg image_id "$expected_both_image_id" \
    --arg receipt_sha256 "$expected_receipt_sha256" \
    --arg lab_head "$(<"$inputs/lab-head.txt")" \
    --arg host_kernel "$expected_host_kernel" --arg host_boot_id "$expected_host_boot_id" \
    --arg inputs_manifest_sha256 "$frozen_inputs_manifest_sha256" \
    --arg cache_manifest_sha256 "$frozen_overlay_cache_manifest_sha256" \
    --arg seed_manifest_sha256 "$expected_seed_manifest_sha256" \
    --arg parent_result_sha256 "$expected_parent_result_sha256" \
    --arg parent_campaign_manifest_sha256 \
      "$expected_parent_campaign_manifest_sha256" \
    --arg parent_cache_manifest_sha256 "$expected_parent_cache_manifest_sha256" \
    --argjson diagnostic_floor "$diagnostic_floor" \
    --argjson strict_floor "$strict_floor" \
    --argjson diagnostic_median "$(read_median_or_null "$fresh_out/bench.json")" \
    --argjson strict_a_median "$(read_median_or_null "$replay_a_out/bench.json")" \
    --slurpfile parent "$inputs/parent-control-result.json" '{
      schema: "neural-download-current-main-tp1-decision-overlay-result-v2",
      state: $state,
      run_root: $run_root,
      classification: $classification,
      failed_arm: $failed_arm,
      failed_speed_gate: {actual_tok_s: $failed_actual, floor_tok_s: $failed_floor},
      completed_model_arms: $completed_arms,
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
      host: {kernel: $host_kernel, boot_id: $host_boot_id},
      parent: {
        state: "complete-speed-only-regression-no-overlay-run",
        aggregate_result_sha256: $parent_result_sha256,
        campaign_manifest_sha256: $parent_campaign_manifest_sha256,
        compiled_cache_manifest_sha256: $parent_cache_manifest_sha256,
        medians_tok_s: $parent[0].medians_tok_s,
        speed_gates: $parent[0].speed_gates,
        all_non_speed_gates_pass: $parent[0].evidence.all_non_speed_gates_pass,
        qualification_ready: $parent[0].qualification_ready,
        same_host_boot: ($parent[0].host.boot_id == $host_boot_id)
      },
      treatment: {
        kind: "best_config-decision-only",
        decision_count: 38,
        seed_manifest_sha256: $seed_manifest_sha256,
        source_overlay: "none",
        compiled_cache_transfer: false,
        all_executables_compiled_fresh: true
      },
      evidence: {
        fresh_current_commit_hardware_gate_pass: true,
        parent_fully_reverified_before_and_after_arms: true,
        frozen_inputs_manifest_sha256: $inputs_manifest_sha256,
        compiled_cache_manifest_sha256: $cache_manifest_sha256,
        seed_unchanged_after_compile_workload_and_shutdown: true,
        no_extra_best_config_records: true,
        complete_cache_file_and_directory_tree_immutable: true,
        exact_source_identity_pre_and_post_completed_arms: true,
        completed_arm_non_speed_gates_pass: true,
        quality_battery_executed: $quality_battery_executed,
        quality_battery_pass: $quality_battery_pass,
        repo_host_and_protected_ledger_postflight_pass: true
      },
      floors_tok_s: {diagnostic: $diagnostic_floor, strict: $strict_floor},
      medians_tok_s: {diagnostic: $diagnostic_median, strict_a: $strict_a_median},
      qualification_ready: false,
      tp2_authorized: false,
      protected_floor_changed: false,
      historical_result_replaced: false
    }' >"$result_tmp"
  mv -f -- "$result_tmp" "$result_root/campaign-result.json"
  sha256sum "$result_root/campaign-result.json" | awk '{print $1}' \
    >"$result_root/.campaign-result.sha256.tmp.$$"
  mv -f -- "$result_root/.campaign-result.sha256.tmp.$$" \
    "$result_root/campaign-result.sha256"
  seal_campaign_status "$terminal_state"
  trap - EXIT
  exit 10
}

write_complete_result() {
  local actual_b=$1 result_tmp qualification_ready terminal_state terminal_rc
  local all_non_speed strict_b_speed_gate
  local replay_b_cache_immutable source_identity_exact arm_out
  verify_inputs
  require_overlay_replay_a
  validate_arm_common "$replay_b_out"
  [[ $(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
       "$replay_b_out/bench.json") == "$actual_b" ]] ||
    die 'overlay replay-B median changed before terminal classification'
  grep -Fqx -e "pass actual=$actual_b floor=$strict_floor" \
    -e "fail actual=$actual_b floor=$strict_floor" \
    "$replay_b_out/decision-overlay-strict-b-gate.status" ||
    die 'overlay replay-B speed gate changed before terminal classification'
  [[ $(sha256sum "$replay_b_out/cache-manifest.pre.sha256" |
       awk '{print $1}') == "$frozen_overlay_cache_manifest_sha256" &&
     $(sha256sum "$replay_b_out/cache-manifest.post.sha256" |
       awk '{print $1}') == "$frozen_overlay_cache_manifest_sha256" ]] ||
    die 'overlay replay-B cache evidence diverges from fresh cache'
  cmp -s "$replay_b_out/cache-manifest.pre.sha256" \
    "$replay_b_out/cache-manifest.post.sha256" ||
    die 'overlay replay B changed the complete cache'
  replay_b_cache_immutable=true
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
  result_tmp="$result_root/.campaign-result.json.tmp.$$"
  jq -n \
    --arg run_root "$result_root" --arg vllm_head "$expected_vllm_head" \
    --arg vllm_tree "$expected_vllm_tree" --arg kernel_head "$expected_kernel_head" \
    --arg kernel_tree "$expected_kernel_tree" --arg base_digest "$expected_base_digest" \
    --arg image_id "$expected_both_image_id" \
    --arg receipt_sha256 "$expected_receipt_sha256" \
    --arg seed_manifest_sha256 "$expected_seed_manifest_sha256" \
    --arg compatibility_metadata_sha256 "$expected_overlay_metadata_sha256" \
    --arg compatibility_census_sha256 "$expected_overlay_census_sha256" \
    --arg inputs_manifest_sha256 "$frozen_inputs_manifest_sha256" \
    --arg cache_manifest_sha256 "$frozen_overlay_cache_manifest_sha256" \
    --arg parent_result_sha256 "$expected_parent_result_sha256" \
    --arg parent_campaign_manifest_sha256 \
      "$expected_parent_campaign_manifest_sha256" \
    --arg parent_cache_manifest_sha256 "$expected_parent_cache_manifest_sha256" \
    --arg lab_head "$(<"$inputs/lab-head.txt")" \
    --arg host_kernel "$expected_host_kernel" \
    --arg host_uname "$(<"$inputs/host-uname.txt")" \
    --arg host_boot_id "$expected_host_boot_id" \
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
    --slurpfile parent "$inputs/parent-control-result.json" \
    --slurpfile q "$replay_a_out/quality.json" '
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
      all($q[0].exact_cases[]; .pass == true) and
      ($q[0].repeat_case.runs | length) == 8 and
      $q[0].repeat_case.pass == true and
      ([ $q[0].repeat_case.runs[].sha256 ] | unique | length) == 1 and
      $q[0].long_context_case.pass == true and
      $q[0].long_context_case.requested_context_tokens == 8192 and
      $q[0].long_context_case.actual_prompt_tokens == 7617 and
      ($q[0].baseline_comparisons | length) == 24 and
      all($q[0].baseline_comparisons[]; . == true))) as $quality_ok |
    (($parent[0].qualification_ready == false and
      $parent[0].speed_gates.diagnostic == true and
      $parent[0].speed_gates.strict_a == false and
      $parent[0].speed_gates.strict_b == false and
      $parent[0].evidence.all_non_speed_gates_pass == true and
      $parent[0].host.boot_id == $host_boot_id)) as $parent_ok |
    (($parent_ok and $source_identity_exact and $model_ok and $canary_ok and
      $bench_ok and $quality_ok and $replay_b_cache_immutable and
      all($pairs[]; .prompt_id_matches))) as $all_non_speed |
    (($all_non_speed and
      $d[0].summary.tok_s_1_100_intervals_after_ttft.median >= $diagnostic_floor and
      $a[0].summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor and
      $b[0].summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor)) as $ready |
    {
      schema: "neural-download-current-main-tp1-decision-overlay-result-v2",
      state: (if $all_non_speed then "complete" else "aggregate-non-speed-failure" end),
      classification: (
        if ($all_non_speed | not) then "aggregate-non-speed-failure"
        elif $ready then "qualified"
        else "complete-quality-clean-speed-only-miss"
        end
      ),
      run_root: $run_root,
      scope: "same-boot sequential overlay qualification; non-interleaved causal attribution",
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
        same_boot_parent_and_all_overlay_arms: $parent_ok
      },
      parent: {
        state: "complete-speed-only-regression-no-overlay-run",
        aggregate_result_sha256: $parent_result_sha256,
        campaign_manifest_sha256: $parent_campaign_manifest_sha256,
        compiled_cache_manifest_sha256: $parent_cache_manifest_sha256,
        medians_tok_s: $parent[0].medians_tok_s,
        speed_gates: $parent[0].speed_gates,
        all_non_speed_gates_pass: $parent[0].evidence.all_non_speed_gates_pass,
        qualification_ready: $parent[0].qualification_ready
      },
      treatment: {
        kind: "best_config-decision-only",
        decision_count: 38,
        seed_manifest_sha256: $seed_manifest_sha256,
        compatibility_metadata_sha256: $compatibility_metadata_sha256,
        compatibility_census_sha256: $compatibility_census_sha256,
        compatible_paths_and_configs_hash: 38,
        normalized_decisions_equal: 24,
        normalized_decisions_different: 14,
        source_overlay: "none",
        compiled_cache_transfer: false,
        all_executables_compiled_fresh: true
      },
      evidence: {
        fresh_current_commit_hardware_gate_pass: true,
        parent_fully_reverified_before_and_after_arms: $parent_ok,
        frozen_inputs_manifest_sha256: $inputs_manifest_sha256,
        compiled_cache_manifest_sha256: $cache_manifest_sha256,
        seed_unchanged_after_compile_workload_and_shutdown: true,
        no_extra_best_config_records: true,
        replay_a_full_cache_immutable: true,
        replay_b_full_cache_immutable: $replay_b_cache_immutable,
        exact_source_identity_pre_and_post_all_arms: $source_identity_exact,
        arm_final_statuses_pass: true,
        repo_host_and_protected_ledger_postflight_pass: true,
        model_identity_all_arms: $model_ok,
        canary_all_arms: $canary_ok,
        realistic_benchmark_all_arms: $bench_ok,
        quality_battery: $quality_ok,
        prompt_order_matches: (all($pairs[]; .prompt_id_matches)),
        all_non_speed_gates_pass: $all_non_speed
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
        prompt_order_gating: true,
        full_token_array_matches: ([$pairs[] | select(.full_token_ids_equal)] | length),
        first_100_token_array_matches: ([$pairs[] | select(.first_100_token_ids_equal)] | length),
        token_array_agreement_gating: false,
        rows: $pairs
      },
      quality: {
        pass_all: $q[0].pass_all,
        baseline_match_all: $q[0].baseline_match_all,
        exact_cases: ($q[0].exact_cases | length),
        repeat_runs: ($q[0].repeat_case.runs | length),
        repeat_unique_hashes: ([ $q[0].repeat_case.runs[].sha256 ] | unique | length),
        long_context_tokens: $q[0].long_context_case.requested_context_tokens,
        long_context_actual_prompt_tokens: $q[0].long_context_case.actual_prompt_tokens,
        baseline_comparisons: ($q[0].baseline_comparisons | length)
      },
      qualification_ready: $ready,
      tp2_authorized: $ready,
      protected_floor_changed: false,
      historical_result_replaced: false
    }' >"$result_tmp"
  mv -f -- "$result_tmp" "$result_root/campaign-result.json"
  sha256sum "$result_root/campaign-result.json" | awk '{print $1}' \
    >"$result_root/.campaign-result.sha256.tmp.$$"
  mv -f -- "$result_root/.campaign-result.sha256.tmp.$$" \
    "$result_root/campaign-result.sha256"
  qualification_ready=$(jq -r .qualification_ready \
    "$result_root/campaign-result.json")
  all_non_speed=$(jq -r .evidence.all_non_speed_gates_pass \
    "$result_root/campaign-result.json")
  strict_b_speed_gate=$(jq -r .speed_gates.strict_b \
    "$result_root/campaign-result.json")
  if [[ $all_non_speed != true ]]; then
    terminal_state=overlay-aggregate-non-speed-failure
    terminal_rc=11
  elif [[ $qualification_ready == true && $strict_b_speed_gate == true ]]; then
    grep -Fqx "pass actual=$actual_b floor=$strict_floor" \
      "$replay_b_out/decision-overlay-strict-b-gate.status" ||
      die 'qualified result lacks the exact replay-B pass gate'
    terminal_state=pass
    terminal_rc=0
  elif [[ $qualification_ready == false && $strict_b_speed_gate == false ]]; then
    grep -Fqx "fail actual=$actual_b floor=$strict_floor" \
      "$replay_b_out/decision-overlay-strict-b-gate.status" ||
      die 'strict-B speed-miss result lacks the exact failed speed gate'
    terminal_state=complete-overlay-strict-b-speed-miss
    terminal_rc=10
  else
    die 'aggregate result has no valid fail-closed terminal classification'
  fi
  seal_campaign_status "$terminal_state"
  trap - EXIT
  exit "$terminal_rc"
}

run_overlay_fresh() {
  local actual
  prepare_inputs
  initialize_common_env
  verify_inputs
  run_strict_arm seeded-fresh-diagnostic "$fresh_out" \
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
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19789 \
      "$fresh_out" "$inputs/validation-suite.json" "$overlay_cache"
  frozen_overlay_cache_manifest_sha256=$(
    <"$fresh_out/cache-manifest.post.sha256.digest"
  )
  [[ $frozen_overlay_cache_manifest_sha256 =~ ^[0-9a-f]{64}$ ]] ||
    die 'seeded-fresh arm did not produce a valid cache-manifest digest'
  freeze_overlay_cache_directories
  validate_fresh_overlay_cache
  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$fresh_out/bench.json")
  write_speed_gate "$fresh_out/decision-overlay-speed-gate.status" \
    "$actual" "$diagnostic_floor"
  verify_inputs
  if grep -q '^fail ' "$fresh_out/decision-overlay-speed-gate.status"; then
    close_speed_only_miss complete-overlay-diagnostic-speed-miss \
      seeded-fresh-diagnostic "$actual" "$diagnostic_floor"
  fi
  write_root_status 'seeded-fresh-pass-awaiting-strict-replay-a'
}

run_overlay_replay_a() {
  local actual
  require_overlay_fresh
  run_strict_arm strict-quality-replay-a "$replay_a_out" \
    run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay \
    EXPECTED_CACHE_MANIFEST_SHA256="$frozen_overlay_cache_manifest_sha256" \
    NATURAL_EOS=1 QUALITY=1 QUALITY_REQUIRE_BASELINE=1 \
    QUALITY_BASELINE_JSON="$inputs/quality-baseline.json" \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19790 \
      "$replay_a_out" "$inputs/validation-suite.json" "$overlay_cache"
  validate_quality_arm
  [[ $(sha256sum "$replay_a_out/cache-manifest.pre.sha256" |
       awk '{print $1}') == "$frozen_overlay_cache_manifest_sha256" &&
     $(sha256sum "$replay_a_out/cache-manifest.post.sha256" |
       awk '{print $1}') == "$frozen_overlay_cache_manifest_sha256" ]] ||
    die 'overlay replay-A cache evidence diverges from fresh cache'
  cmp -s "$replay_a_out/cache-manifest.pre.sha256" \
    "$replay_a_out/cache-manifest.post.sha256" ||
    die 'overlay replay A changed the complete cache'
  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$replay_a_out/bench.json")
  write_speed_gate "$replay_a_out/decision-overlay-strict-a-gate.status" \
    "$actual" "$strict_floor"
  verify_inputs
  if grep -q '^fail ' "$replay_a_out/decision-overlay-strict-a-gate.status"; then
    close_speed_only_miss complete-overlay-strict-a-speed-miss \
      strict-quality-replay-a "$actual" "$strict_floor"
  fi
  write_root_status 'strict-replay-a-pass-awaiting-strict-replay-b'
}

run_overlay_replay_b() {
  local actual
  require_overlay_replay_a
  run_strict_arm strict-replay-b "$replay_b_out" \
    run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay \
    EXPECTED_CACHE_MANIFEST_SHA256="$frozen_overlay_cache_manifest_sha256" \
    NATURAL_EOS=1 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$inputs/strict-smoke.sh" both 0 f16 32768 0 19791 \
      "$replay_b_out" "$inputs/validation-suite.json" "$overlay_cache"
  validate_arm_common "$replay_b_out"
  [[ $(sha256sum "$replay_b_out/cache-manifest.pre.sha256" |
       awk '{print $1}') == "$frozen_overlay_cache_manifest_sha256" &&
     $(sha256sum "$replay_b_out/cache-manifest.post.sha256" |
       awk '{print $1}') == "$frozen_overlay_cache_manifest_sha256" ]] ||
    die 'overlay replay-B cache evidence diverges from fresh cache'
  cmp -s "$replay_b_out/cache-manifest.pre.sha256" \
    "$replay_b_out/cache-manifest.post.sha256" ||
    die 'overlay replay B changed the complete cache'
  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$replay_b_out/bench.json")
  write_speed_gate "$replay_b_out/decision-overlay-strict-b-gate.status" \
    "$actual" "$strict_floor"
  write_complete_result "$actual"
}

for required in "$runner" "$kernel_delta_classifier" \
    "$kernel_delta_classifier_test" "$hardware_gate_runner" "$receipt" \
    "$suite" "$baseline" "$model_manifest" "$model_verifier" \
    "$bench_helper" "$quality_helper" "$prereg" "$parent_record" \
    "$parent_closeout" "$stale_record" "$stale_closeout" \
    "$protected_manifest"; do
  [[ -e $required ]] || die "missing input: $required"
done
[[ -r $sudo_pass_file ]] || die 'sudo password file is unreadable'
[[ $(sha256sum "$suite" | awk '{print $1}') == "$expected_suite_sha256" ]] ||
  die 'validation suite hash changed'
[[ $(sha256sum "$baseline" | awk '{print $1}') == \
   "$expected_baseline_sha256" ]] || die 'quality baseline hash changed'
[[ $(sha256sum "$receipt" | awk '{print $1}') == \
   "$expected_receipt_sha256" ]] || die 'exact 6a9c build receipt changed'
[[ $(sha256sum "$prereg" | awk '{print $1}') == \
   "$expected_prereg_sha256" ]] || die 'overlay preregistration changed'
[[ $(sha256sum "$runner" | awk '{print $1}') == \
   "$expected_runner_sha256" ]] || die 'successful benchmark runner changed'
[[ $(sha256sum "$kernel_delta_classifier" | awk '{print $1}') == \
   "$expected_kernel_delta_classifier_sha256" ]] ||
  die 'kernel-delta classifier changed'
[[ $(sha256sum "$kernel_delta_classifier_test" | awk '{print $1}') == \
   "$expected_kernel_delta_classifier_test_sha256" ]] ||
  die 'kernel-delta classifier test changed'
[[ $(sha256sum "$hardware_gate_runner" | awk '{print $1}') == \
   "$expected_hardware_gate_runner_sha256" ]] ||
  die 'hardware-gate runner changed'
[[ -x $classifier_test_python ]] || die 'classifier-test Python is not executable'
if classifier_test_receipt=$(PATH="$(dirname -- "$classifier_test_python"):/usr/bin:/bin" \
    PYTHONDONTWRITEBYTECODE=1 "$classifier_test_python" \
    "$kernel_delta_classifier_test" 2>&1); then
  :
else
  die "kernel-delta classifier test failed: $classifier_test_receipt"
fi
verify_build_receipt
verify_decision_bundle
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
timeout --signal=TERM --kill-after=5s 20s sudo -S -p '' -v \
  <"$sudo_pass_file" || die 'sudo authentication preflight failed'
verify_parent_campaign
verify_stale_predecessor

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
[[ $(timeout --signal=TERM --kill-after=5s 30s \
    git ls-remote --exit-code \
    https://github.com/vllm-project/vllm-xpu-kernels.git refs/heads/main |
    awk 'NR == 1 {print $1}') == "$expected_kernel_head" ]] ||
  die 'XPU-kernel main advanced before the hardware gate; rebuild first'
live_base_digest=$(timeout --signal=TERM --kill-after=5s 60s \
  sudo -S -p '' docker buildx imagetools inspect \
  vllm/vllm-openai-xpu:nightly --format '{{.Manifest.Digest}}' \
  <"$sudo_pass_file")
[[ $live_base_digest == "$expected_base_digest" ]] ||
  die 'official nightly advanced before the hardware gate; rebuild first'

for frozen_root in "$parent_root" "$parent_hardware" "$stale_root" \
    "$stale_hardware" "$hardware_gate" "$result_root"; do
  [[ $frozen_root == /* && $(realpath -m -- "$frozen_root") == "$frozen_root" ]] ||
    die "campaign root is not absolute and canonical: $frozen_root"
done
for protected_root in "$parent_root" "$parent_hardware" "$stale_root" \
    "$stale_hardware"; do
  if [[ $result_root == "$protected_root" ||
        $result_root == "$protected_root/"* ||
        $protected_root == "$result_root/"* ||
        $hardware_gate == "$protected_root" ||
        $hardware_gate == "$protected_root/"* ||
        $protected_root == "$hardware_gate/"* ]]; then
    die 'fresh roots overlap sealed parent or predecessor evidence'
  fi
done
if [[ $result_root == "$hardware_gate" ||
      $result_root == "$hardware_gate/"* ||
      $hardware_gate == "$result_root/"* ]]; then
  die 'campaign and fresh hardware-gate roots overlap'
fi
[[ ! -e $result_root ]] || die "result root already exists: $result_root"
[[ ! -e $hardware_gate ]] ||
  die "fresh hardware-gate root already exists: $hardware_gate"
result_parent=$(dirname -- "$result_root")
hardware_parent=$(dirname -- "$hardware_gate")
[[ -d $result_parent && -d $hardware_parent ]] ||
  die 'campaign and hardware-gate parents must already exist'
[[ $(findmnt -n -o FSTYPE --target "$result_parent") == ext4 &&
   $(findmnt -n -o FSTYPE --target "$hardware_parent") == ext4 ]] ||
  die 'campaign and fresh hardware-gate evidence must be on ext4'
available_kib=$(df -Pk "$result_parent" | awk 'NR == 2 {print $4}')
[[ $available_kib =~ ^[0-9]+$ ]] || die 'could not read qualification free space'
(( available_kib >= 12 * 1024 * 1024 )) ||
  die 'qualification requires at least 12 GiB free'
[[ $(sudo -S -p '' docker image inspect "$expected_control_image_id" \
    --format '{{.Id}}' <"$sudo_pass_file") == "$expected_control_image_id" ]] ||
  die 'exact 6a9c stock-kernel image is absent'
[[ $(sudo -S -p '' docker image inspect "$expected_both_image_id" \
    --format '{{.Id}}' <"$sudo_pass_file") == "$expected_both_image_id" ]] ||
  die 'exact 6a9c both-current image is absent'
sudo -S -p '' docker image inspect "$expected_both_image_id" \
  <"$sudo_pass_file" |
  jq -e 'all((.[0].Config.Env // [])[];
    startswith("VLLM_BATCH_INVARIANT=") | not)' >/dev/null ||
  die 'measured image unexpectedly sets VLLM_BATCH_INVARIANT'

acquire_campaign_locks
RESULT_ROOT="$hardware_gate" SUDO_PASS_FILE="$sudo_pass_file" \
QWEN_CURRENT_MUSE_LOCK_FD="$campaign_muse_lock_fd" \
QWEN_CURRENT_HOST_LOCK_FD="$campaign_host_lock_fd" \
QWEN_CURRENT_GPU_LEASE_FDS="$campaign_gpu_lease_csv" \
  "$hardware_gate_runner"
validate_hardware_gate

trap root_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
run_overlay_fresh
run_overlay_replay_a
run_overlay_replay_b
