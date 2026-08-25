#!/usr/bin/env bash
set -Eeuo pipefail

# Atomic TP4 zero-overlay qualification for the frozen b2dd/1e90 campaign.
# Remote upstream movement is intentionally non-gating; exact local source,
# image, input, hardware, topology, cache, workload, and quality gates remain
# hard requirements.

umask 077

mode=${1:-all}
[[ $# -le 1 && $mode == all ]] || {
  printf 'usage: %s all\n' "$0" >&2
  printf 'the three-arm packet is atomic and cannot resume individual arms\n' >&2
  exit 2
}

script_path=$(realpath -e -- "${BASH_SOURCE[0]}")
script_dir=$(dirname -- "$script_path")
repo=$(git -C "$script_dir" rev-parse --show-toplevel)
lane=$repo/experiments/qwen38-27b-b70
runner=$lane/scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh
hardware_runner=$lane/scripts/run-20260824-qwen38-known-nvme-aware-hardware-gate.sh
freeze=$lane/data/2026-08-25-qwen38-b2dd9ce73d-campaign-freeze.json
receipt=$lane/data/2026-08-24-qwen38-b2dd9ce73d-absolute-current-main-build.json
prereg=$lane/notes/2026-08-25-qwen38-b2dd9ce73d-tp4-zero-overlay-r1-prereg.md
protected_manifest=$lane/data/2026-08-23-qwen38-current-main-overlay-manifest.json
tp4_overlay=$lane/autotune-winner-overlays/tp4-e9d1398-best-config
suite=$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json
baseline=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp4-mtp0-f16-graph-natural-eos-replay-a-baseline-quality/quality.json
model_manifest=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json
model_verifier=$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py
bench_helper=$repo/scripts/bench-openai-realistic-suite.py
quality_helper=$repo/scripts/qwen38-text-quality-suite.py
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}

readonly hardware_gate=/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-b2dd9ce73d-tp4-20260825-086de284-r1
readonly result_root=/home/steve/qwen38-current-main-runs/tp4-untreated-b2dd9ce73d-20260825-r1
readonly cache=$result_root/control-cache
readonly fresh_out=$result_root/control-fresh-diagnostic
readonly replay_a_out=$result_root/control-strict-quality-replay-a
readonly replay_b_out=$result_root/control-strict-replay-b
readonly inputs=$result_root/inputs

readonly image_repository=neural-download/vllm-openai-xpu
readonly image_tag=neural-download/vllm-openai-xpu:vllm-b2dd9ce73d-kernel-1e90ffa672-official
readonly image_id=sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296
readonly image_repo_digest=sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296
readonly expected_vllm_head=b2dd9ce73dce2ad09007d1db5c171454118981d7
readonly expected_vllm_tree=65c93c14916a9a895c5592b8a0ba2803efc96346
readonly expected_vllm_version=0.26.1rc1.dev1172+gb2dd9ce73.xpu
readonly expected_kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
readonly expected_kernel_version=0.1.dev1+g1e90ffa67
readonly expected_base_digest=sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876
readonly source_identity_path=/opt/neural-download/source-identity.json
readonly source_identity_sha=2a0ee74968dd68ba15b31eeef3e404807d125e6e52a0e96d25e8b955bd4ae0a0
readonly expected_boot_id=086de284-0771-4269-9cb2-e064fe303e40
readonly expected_host_kernel=7.0.0-30-generic

readonly freeze_sha=54f6303a7864cb2263818bc55370606df2535c689a06011dd97d2eddcbd8ac2c
readonly receipt_sha=d56dc84c1137d741042b2e295c6b1f6a40bf28a3c56e0c52761dd725e3a5caa0
readonly prereg_sha=8d124c02872c799734d43db3956a35f63b258b7a8a514fa403e587f2a0dc5c25
readonly runner_sha=cb2bfd95e7ad9956dae5bc22ccfa575c8742847c963143291a21505533598202
readonly hardware_runner_sha=8038015b179048662f53d7d41ead6cddc95671081942444f394c6e48ed57a6f7
readonly suite_sha=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
readonly baseline_sha=8215fb791e11b3e4c09056b4979c4739d3d855f2086c4786d45f2053c0342488
readonly model_manifest_sha=731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
readonly model_verifier_sha=5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
readonly bench_helper_sha=442e9777d864f94eca82424929d3875ac15a155fd9e510e5054ef199a9751ab4
readonly quality_helper_sha=67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d
readonly protected_manifest_sha=4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454
readonly protected_values_sha=e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f
readonly tp4_overlay_manifest_sha=a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2

readonly diagnostic_floor=71.5488
readonly strict_each_floor=71.29326283364946
readonly strict_one_floor=71.39843006187554
readonly required_free_kib=12582912
readonly extra_args_json='["--pipeline-parallel-size","1","--data-parallel-size","1","--enable-chunked-prefill","--async-scheduling","--compilation-config","{\"cudagraph_mode\":\"FULL_AND_PIECEWISE\",\"cudagraph_capture_sizes\":[1,2],\"max_cudagraph_capture_size\":2}"]'

failure_stage=static-preflight
failure_reason=
campaign_lab_head=

die() {
  failure_reason=$*
  printf 'error: %s\n' "$*" >&2
  exit 1
}

dockerc() {
  sudo -S -p '' docker "$@" <"$sudo_pass_file"
}

check_sha() {
  local path=$1 expected=$2 actual
  [[ -f $path ]] || die "missing input: $path"
  actual=$(sha256sum "$path" | awk '{print $1}')
  [[ $actual == "$expected" ]] || die "hash mismatch for $path: $actual"
}

acquire_locks() {
  local device lease_fd
  exec {muse_lock_fd}<>/run/lock/muse-glimmer-gpu-exclusive.lock
  flock -n "$muse_lock_fd" || die 'Muse GPU lock is held'
  exec {host_lock_fd}<>/tmp/b70-benchmark.lock
  flock -n "$host_lock_fd" || die 'host benchmark lock is held'
  gpu_lease_dir=/run/user/$(id -u)/qwen36-b70-gpu-leases
  mkdir -p -- "$gpu_lease_dir"
  gpu_lease_fds=()
  for device in 0 1 2 3; do
    exec {lease_fd}>"$gpu_lease_dir/gpu${device}.lock"
    flock -n "$lease_fd" || die "GPU $device is leased"
    gpu_lease_fds+=("$lease_fd")
  done
  gpu_lease_csv=$(IFS=,; printf '%s' "${gpu_lease_fds[*]}")
}

outer_cache_manifest() {
  local destination=$1
  sudo -S -p '' bash -c '
    cd "$1" || exit 1
    find . -type f -print0 | sort -z | xargs -0 -r sha256sum
  ' bash "$cache" <"$sudo_pass_file" >"$destination"
}

validate_hardware_gate() {
  (
    cd "$hardware_gate"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die 'hardware-gate evidence manifest failed'
  [[ $(<"$hardware_gate/final.status") == exit_status=0 ]] ||
    die 'hardware gate did not exit cleanly'
  jq -e --arg boot "$expected_boot_id" --arg kernel "$expected_host_kernel" \
    --arg head "$(git -C "$repo" rev-parse HEAD)" '
      .passed == true and .gate_complete == true and .failure_stage == "complete" and
      .host.boot_id == $boot and .host.kernel == $kernel and .repo_head == $head and
      .gates.four_device_identity == true and .gates.per_card_compute == true and
      .gates.four_device_peer_read == true and
      .gates.four_rank_xccl_allreduce == true and
      .gates.repo_postflight == true and .gates.atomic_lock_handoff == true and
      .gates.torch_runtime_coherent == true and .gates.root_nvme_health == true and
      .gates.selector_and_mask_combined == false and
      .gates.kernel_reject_events == 0
    ' "$hardware_gate/summary.json" >/dev/null || die 'hardware gate is invalid'
}

verify_protected_history() {
  [[ $(sha256sum "$protected_manifest" | awk '{print $1}') == \
     "$protected_manifest_sha" ]] || die 'protected manifest changed'
  [[ $(jq -cS '.protected_target_only_decode_tok_s' "$protected_manifest" |
      sha256sum | awk '{print $1}') == "$protected_values_sha" ]] ||
    die 'protected performance ledger changed'
  jq -e '
    .protected_target_only_decode_tok_s.pinned_diagnostic.tp4 == [71.6741, 71.5488] and
    .protected_target_only_decode_tok_s.pinned_strict.tp4 == [71.29326283364946, 71.39843006187554] and
    .protected_target_only_decode_tok_s.a356_stock_strict.tp4[0] == 71.9001988117144 and
    .protected_target_only_decode_tok_s.a356_tp4_decision_overlay_diagnostic == [71.72254506718171] and
    .protected_target_only_decode_tok_s.a356_tp4_decision_overlay_strict == [71.35287190161719, 71.45427094575045]
  ' "$protected_manifest" >/dev/null || die 'protected TP4 values changed'
  [[ $(sha256sum "$tp4_overlay/manifest.sha256" | awk '{print $1}') == \
     "$tp4_overlay_manifest_sha" ]] || die 'historical TP4 overlay manifest changed'
  (
    cd "$tp4_overlay/source"
    sha256sum -c ../manifest.sha256 >/dev/null
  ) || die 'historical TP4 overlay payload changed'
  [[ $(find "$tp4_overlay/source" -type f -name '*.best_config' | wc -l) -eq 152 ]] ||
    die 'historical TP4 overlay count changed'
}

verify_frozen_identity() {
  jq -e --arg vllm "$expected_vllm_head" --arg tree "$expected_vllm_tree" \
    --arg kernel "$expected_kernel_head" --arg base "$expected_base_digest" \
    --arg image "$image_id" --arg receipt "$receipt_sha" \
    --arg source_path "$source_identity_path" --arg source_sha "$source_identity_sha" '
      .policy.engine_identity_frozen_at_first_arm == true and
      .policy.later_remote_upstream_movement_is_gating == false and
      .policy.local_lab_head_and_worktree_are_gating == true and
      .policy.arm_inputs_are_copied_and_hash_locked == true and
      .source_identity.vllm_head == $vllm and .source_identity.vllm_tree == $tree and
      .source_identity.xpu_kernel_head == $kernel and
      .source_identity.nightly_dependency_base_digest == $base and
      .source_identity.image_id == $image and
      .source_identity.embedded_source_identity_path == $source_path and
      .source_identity.embedded_source_identity_sha256 == $source_sha and
      .source_identity.build_receipt_sha256 == $receipt and
      .protected_performance.lowering_or_replacement_allowed == false
    ' "$freeze" >/dev/null || die 'campaign freeze record is incoherent'
  jq -e --arg vllm "$expected_vllm_head" --arg tree "$expected_vllm_tree" \
    --arg kernel "$expected_kernel_head" --arg base "$expected_base_digest" \
    --arg image "$image_id" '
      .vllm.head == $vllm and .vllm.tree == $tree and
      .kernel.head == $kernel and .base_digest == $base and
      .images.both_current_zero_overlay.image_id == $image and
      .images.both_current_zero_overlay.static_preflight_passed == true
    ' "$receipt" >/dev/null || die 'build receipt is incoherent'
}

verify_frozen_lab_inputs() {
  [[ -n $campaign_lab_head ]] || die 'campaign lab head is unset'
  [[ $(git -C "$repo" rev-parse HEAD) == "$campaign_lab_head" ]] ||
    die 'local lab HEAD changed during campaign'
  [[ -z $(git -C "$repo" status --porcelain) ]] ||
    die 'local lab worktree changed during campaign'
  (
    cd "$inputs"
    sha256sum -c SHA256SUMS >/dev/null
  ) || die 'frozen campaign input manifest changed'
}

verify_arm_identity() {
  local out=$1 expected_natural=$2 expected_quality=$3
  [[ $(<"$out/image-id.txt") == "$image_id" &&
     $(<"$out/container-image-id.txt") == "$image_id" ]] ||
    die "wrong image in $out"
  [[ $(sed -n '1p' "$out/vllm-source-commit.txt") == "$expected_vllm_head" ]] ||
    die "wrong vLLM source in $out"
  [[ $(sha256sum "$out/source-identity.json" | awk '{print $1}') == \
     "$source_identity_sha" ]] || die "wrong embedded source identity in $out"
  jq -e --arg vllm "$expected_vllm_head" --arg tree "$expected_vllm_tree" \
    --arg kernel "$expected_kernel_head" --arg base "$expected_base_digest" '
      .overlay == "none" and .vllm.head == $vllm and .vllm.tree == $tree and
      .kernel.head == $kernel and .base_digest == $base
    ' "$out/source-identity.json" >/dev/null || die "incoherent source identity in $out"
  grep -Fx "vllm $expected_vllm_version" "$out/stack-versions.txt" >/dev/null ||
    die "wrong vLLM package in $out"
  grep -Fx "vllm-xpu-kernels $expected_kernel_version" "$out/stack-versions.txt" >/dev/null ||
    die "wrong XPU kernel package in $out"
  grep -Fx 'tp=4' "$out/identity.env" >/dev/null &&
    grep -Fx 'gpus=0,1,2,3' "$out/identity.env" >/dev/null &&
    grep -Fx 'mtp=0' "$out/identity.env" >/dev/null &&
    grep -Fx 'kv=f16' "$out/identity.env" >/dev/null &&
    grep -Fx 'max_model_len=32768' "$out/identity.env" >/dev/null &&
    grep -Fx 'gpu_memory_utilization=0.60' "$out/identity.env" >/dev/null &&
    grep -Fx 'vllm_xpu_graph=1' "$out/identity.env" >/dev/null &&
    grep -Fx 'pythonhashseed=unset' "$out/identity.env" >/dev/null &&
    grep -Fx 'prompt_ids=all' "$out/identity.env" >/dev/null &&
    grep -Fx "natural_eos=$expected_natural" "$out/identity.env" >/dev/null &&
    grep -Fx "quality=$expected_quality" "$out/identity.env" >/dev/null &&
    grep -Fx "quality_require_baseline=$expected_quality" "$out/identity.env" >/dev/null ||
    die "wrong topology or environment in $out"
  jq -Rse --arg model /mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan '
    split("\n")[:-1] == [
      $model, "--host", "0.0.0.0", "--port", "8000", "--trust-remote-code",
      "--served-model-name", "qwen38-rolling-nightly-strict",
      "--tensor-parallel-size", "4", "--max-model-len", "32768",
      "--max-num-seqs", "1", "--max-num-batched-tokens", "1024",
      "--gpu-memory-utilization", "0.60", "--dtype", "float16",
      "--reasoning-parser", "qwen3", "--default-chat-template-kwargs",
      "{\"enable_thinking\": false}", "--enable-prompt-tokens-details",
      "--no-enable-prefix-caching", "--pipeline-parallel-size", "1",
      "--data-parallel-size", "1", "--enable-chunked-prefill",
      "--async-scheduling", "--compilation-config",
      "{\"cudagraph_mode\":\"FULL_AND_PIECEWISE\",\"cudagraph_capture_sizes\":[1,2],\"max_cudagraph_capture_size\":2}"
    ]
  ' <"$out/server-args.txt" >/dev/null || die "wrong server arguments in $out"
  jq -e '.status == "verified" and (.files | length) == 19 and
    all(.files[]; .direct_ok == true and .ordinary_ok == true and
      .paths_coherent == true and .ok == true)' \
    "$out/model-direct-and-ordinary-verify.json" >/dev/null ||
    die "model verification failed in $out"
  jq -e '.content == "14" and .cached_tokens == 0' "$out/canary.json" >/dev/null ||
    die "canary failed in $out"
  jq -e '
    (.rows | length) == 25 and .fresh_response_validity.valid == true and
    .fresh_response_validity.prompt_count == 25 and
    .fresh_response_validity.prompts_are_unique == true and
    .fresh_response_validity.return_token_ids_requested == true and
    .fresh_response_validity.cached_tokens_all_zero == true and
    .realistic_final_gate.passed == true and
    .realistic_final_gate.metric_events == 100 and
    .realistic_final_gate.metric_intervals == 99 and
    .realistic_final_gate.cached_tokens_all_zero == true
  ' "$out/bench.json" >/dev/null || die "benchmark gates failed in $out"
}

run_arm() {
  local cache_policy=$1 natural=$2 quality=$3 port=$4 out=$5 expected_manifest=${6:-}
  local arm_rc=0 container_name="qwen38-rolling-nightly-strict-${port}"
  local -a replay_env=()
  if [[ $cache_policy == replay ]]; then
    replay_env=(EXPECTED_CACHE_MANIFEST_SHA256="$expected_manifest")
  fi
  env -u PYTHONHASHSEED -u VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE \
    -u VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING \
    -u TRITON_CACHE_AUTOTUNING -u VLLM_XPU_ENABLE_XPU_GRAPH \
    -u EXTRA_VLLM_ARGS -u EXTRA_VLLM_ARGS_JSON -u PROMPT_IDS \
    -u ONEAPI_DEVICE_SELECTOR -u ZE_AFFINITY_MASK \
    -u SYCL_DEVICE_FILTER -u SYCL_DEVICE_ALLOWLIST -u UR_DEVICE_SELECTORS \
    -u XPU_GRAPH -u COMPILATION_CONFIG \
    -u PYTHONPATH -u PYTHONHOME -u LD_PRELOAD -u LD_LIBRARY_PATH \
    -u QUALITY_BASELINE_JSON -u QUALITY_REQUIRE_BASELINE \
    -u CACHE_POLICY -u EXPECTED_CACHE_MANIFEST_SHA256 \
    -u BEST_CONFIG_SEED_DIR -u EXPECTED_BEST_CONFIG_SEED_COUNT \
    -u EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256 \
    -u BEST_CONFIG_TARGET_AOT_NAMESPACE \
    -u EXPECTED_CACHE_OUTER_NAMESPACE -u EXPECTED_CACHE_CODE_HASH \
    -u EXPECTED_CACHE_COMPILER_HASH -u EXPECTED_CACHE_CONFIG_HASH \
    -u EXPECTED_CACHE_ENV_SHA256 -u EXPECTED_COMPUTATION_GRAPH_SHA256S \
    -u VLLM_BATCH_INVARIANT \
    SUDO_PASS_FILE="$sudo_pass_file" \
    LAB_REPO_ROOT="$repo" \
    MODEL_MANIFEST_PATH="$inputs/$(basename -- "$model_manifest")" \
    MODEL_VERIFIER_PATH="$inputs/$(basename -- "$model_verifier")" \
    BENCH_HELPER_PATH="$inputs/$(basename -- "$bench_helper")" \
    QUALITY_HELPER_PATH="$inputs/$(basename -- "$quality_helper")" \
    SOURCE_IMAGE_REPOSITORY="$image_repository" SOURCE_IMAGE_TAG="$image_tag" \
    PULL_SOURCE_IMAGE=0 EXPECTED_RESOLVED_IMAGE_DIGEST="$image_repo_digest" \
    EXPECTED_IMAGE_ID="$image_id" CACHE_POLICY="$cache_policy" \
    SOURCE_IDENTITY_PATH="$source_identity_path" \
    EXPECTED_SOURCE_IDENTITY_SHA256="$source_identity_sha" \
    VLLM_XPU_GRAPH=1 REQUIRE_GRAPH_CAPTURE=1 GPU_MEM_UTIL=0.60 \
    EXTRA_VLLM_ARGS_JSON="$extra_args_json" MAX_TOKENS=512 \
    RETURN_TOKEN_IDS=1 CANARY=1 BENCH=1 NATURAL_EOS="$natural" QUALITY="$quality" \
    "${replay_env[@]}" \
    QUALITY_BASELINE_JSON="$inputs/$(basename -- "$baseline")" \
    QUALITY_REQUIRE_BASELINE="$quality" \
    "$inputs/$(basename -- "$runner")" 0 f16 32768 0,1,2,3 "$port" "$out" \
    "$inputs/$(basename -- "$suite")" "$cache" || arm_rc=$?
  [[ -z $(dockerc ps -aq --filter "name=^/${container_name}$") ]] ||
    die "arm container survived cleanup: $container_name"
  ! ss -H -ltn | awk '{print $4}' | grep -Eq "(^|:)$port$" ||
    die "arm port survived cleanup: $port"
  verify_frozen_lab_inputs
  (( arm_rc == 0 )) || die "arm runner failed for $out with rc=$arm_rc"
  verify_arm_identity "$out" "$natural" "$quality"
}

write_campaign_manifest() {
  local tmp=$result_root/.campaign-evidence.sha256.tmp
  (
    cd "$result_root"
    find . -type f ! -name 'campaign-evidence.sha256*' -print0 |
      sort -z | xargs -0 -r sha256sum
  ) >"$tmp"
  mv -- "$tmp" "$result_root/campaign-evidence.sha256"
  sha256sum "$result_root/campaign-evidence.sha256" |
    awk '{print $1}' >"$result_root/campaign-evidence.sha256.digest"
}

finalize() {
  local rc=$?
  trap - EXIT
  set +e
  if [[ -d $result_root ]]; then
    if [[ ! -f $result_root/final.status ]]; then
      printf 'fail rc=%s stage=%s reason=%s\n' "$rc" "$failure_stage" \
        "${failure_reason:-unexpected command failure}" >"$result_root/final.status"
    fi
    write_campaign_manifest
    sync -f "$result_root"
  fi
  exit "$rc"
}
trap finalize EXIT

for command_name in awk cmp date df docker env find findmnt flock git jq mv pgrep \
  realpath sha256sum sort ss sudo sync uname wc xargs; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done
[[ -r $sudo_pass_file ]] || die 'sudo password file is unreadable'
[[ -z $(git -C "$repo" status --porcelain) ]] || die 'lab repo must be clean'
[[ $(git -C "$repo" branch --show-current) == main ]] || die 'lab repo is not on main'
campaign_lab_head=$(git -C "$repo" rev-parse HEAD)
[[ $campaign_lab_head == $(git -C "$repo" rev-parse origin/main) ]] ||
  die 'lab main is not pushed to origin/main'
[[ $(</proc/sys/kernel/random/boot_id) == "$expected_boot_id" ]] ||
  die 'host boot changed'
[[ $(uname -r) == "$expected_host_kernel" ]] || die 'host kernel changed'
[[ $(findmnt -n -o FSTYPE -T /home/steve) == ext4 ]] || die 'run root is not ext4'
(( $(df -Pk /home/steve | awk 'NR == 2 {print $4}') >= required_free_kib )) ||
  die 'less than 12 GiB is free on the run filesystem'
[[ ! -e $hardware_gate && ! -e $result_root ]] || die 'fresh run roots are not absent'
for port in 19840 19841 19842; do
  ! ss -H -ltn | awk '{print $4}' | grep -Eq "(^|:)$port$" ||
    die "port $port is already bound"
done
[[ -z $(dockerc ps -q) ]] || die 'a container is already running'
! pgrep -af '[v]llm serve|[E]ngineCore' >/dev/null || die 'a model server is running'

check_sha "$freeze" "$freeze_sha"
check_sha "$receipt" "$receipt_sha"
check_sha "$prereg" "$prereg_sha"
check_sha "$runner" "$runner_sha"
check_sha "$hardware_runner" "$hardware_runner_sha"
check_sha "$suite" "$suite_sha"
check_sha "$baseline" "$baseline_sha"
check_sha "$model_manifest" "$model_manifest_sha"
check_sha "$model_verifier" "$model_verifier_sha"
check_sha "$bench_helper" "$bench_helper_sha"
check_sha "$quality_helper" "$quality_helper_sha"
verify_frozen_identity
verify_protected_history
[[ $(dockerc image inspect --format '{{.Id}}' "$image_tag") == "$image_id" ]] ||
  die 'exact frozen image is absent'

failure_stage=hardware-gate
acquire_locks
RESULT_ROOT="$hardware_gate" SUDO_PASS_FILE="$sudo_pass_file" \
QWEN_CURRENT_MUSE_LOCK_FD="$muse_lock_fd" \
QWEN_CURRENT_HOST_LOCK_FD="$host_lock_fd" \
QWEN_CURRENT_GPU_LEASE_FDS="$gpu_lease_csv" \
  "$hardware_runner"
validate_hardware_gate

failure_stage=prepare-inputs
mkdir -p -- "$inputs"
for input in "$script_path" "$runner" "$hardware_runner" "$freeze" "$receipt" \
  "$prereg" "$suite" "$baseline" "$model_manifest" "$model_verifier" \
  "$bench_helper" "$quality_helper" "$protected_manifest"; do
  cp --reflink=never -- "$input" "$inputs/$(basename -- "$input")"
done
printf '%s\n' "$campaign_lab_head" >"$inputs/lab-head.txt"
sha256sum "$inputs"/* >"$inputs/SHA256SUMS"
verify_frozen_lab_inputs

failure_stage=fresh-diagnostic
run_arm fresh 0 0 19840 "$fresh_out"
outer_cache_manifest "$fresh_out/cache-manifest.outer-final.sha256"
cmp -s "$fresh_out/cache-manifest.post.sha256" \
  "$fresh_out/cache-manifest.outer-final.sha256" || die 'fresh cache changed after cleanup'
cache_manifest_sha=$(sha256sum "$fresh_out/cache-manifest.outer-final.sha256" |
  awk '{print $1}')

failure_stage=strict-quality-replay-a
run_arm replay 1 1 19841 "$replay_a_out" "$cache_manifest_sha"
outer_cache_manifest "$replay_a_out/cache-manifest.outer-final.sha256"
cmp -s "$fresh_out/cache-manifest.outer-final.sha256" \
  "$replay_a_out/cache-manifest.outer-final.sha256" || die 'replay A changed cache'
jq -e '
  .pass_all == true and .baseline_match_all == true and
  (.exact_cases | length) == 7 and all(.exact_cases[]; .pass == true) and
  .repeat_case.pass == true and .repeat_case.repeats == 8 and
  (.repeat_case.runs | length) == 8 and
  (.repeat_case.unique_hashes | length) == 1 and
  .long_context_case.pass == true and
  .long_context_case.requested_context_tokens == 8192 and
  (.baseline_comparisons | length) == 24 and
  all(.baseline_comparisons | to_entries[]; .value == true) and
  ([paths(scalars) as $p | select(($p[-1] == "cached_tokens")) | getpath($p)] |
    length == 16 and all(. == 0))
' "$replay_a_out/quality.json" >/dev/null || die 'strict A quality battery failed'

failure_stage=strict-replay-b
run_arm replay 1 0 19842 "$replay_b_out" "$cache_manifest_sha"
outer_cache_manifest "$replay_b_out/cache-manifest.outer-final.sha256"
cmp -s "$fresh_out/cache-manifest.outer-final.sha256" \
  "$replay_b_out/cache-manifest.outer-final.sha256" || die 'replay B changed cache'

failure_stage=aggregate
diagnostic=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' "$fresh_out/bench.json")
strict_a=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' "$replay_a_out/bench.json")
strict_b=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' "$replay_b_out/bench.json")
diagnostic_pass=$(awk -v value="$diagnostic" -v floor="$diagnostic_floor" \
  'BEGIN {print value >= floor ? "true" : "false"}')
strict_pass=$(awk -v a="$strict_a" -v b="$strict_b" -v each="$strict_each_floor" \
  -v one="$strict_one_floor" 'BEGIN {high=(a>b?a:b); print a>=each && b>=each && high>=one ? "true" : "false"}')

jq -n --arg created_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg vllm "$expected_vllm_head" --arg kernel "$expected_kernel_head" \
  --arg image "$image_id" --arg cache_manifest_sha "$cache_manifest_sha" \
  --argjson diagnostic "$diagnostic" --argjson strict_a "$strict_a" \
  --argjson strict_b "$strict_b" --argjson diagnostic_pass "$diagnostic_pass" \
  --argjson strict_pass "$strict_pass" ' {
    schema: "neural-download-qwen38-frozen-tp4-zero-overlay-result-v1",
    created_utc: $created_utc,
    classification: (if $diagnostic_pass and $strict_pass then
      "complete-qualified-frozen-snapshot" else "complete-measured-speed-regression" end),
    source: {vllm_head: $vllm, xpu_kernel_head: $kernel, image_id: $image,
      live_remote_upstream_gating: false},
    topology: {tp: 4, gpus: [0,1,2,3], mtp: 0, kv: "f16", graph: "FULL_AND_PIECEWISE",
      max_model_len: 32768, gpu_memory_utilization: 0.60, pythonhashseed: "unset",
      source_overlay: "none", decision_overlay: "none"},
    results: {
      diagnostic: {decode_tok_s: $diagnostic, floor: 71.5488, pass: $diagnostic_pass},
      strict_a: {decode_tok_s: $strict_a, floor: 71.29326283364946,
        full_quality_pass: true},
      strict_b: {decode_tok_s: $strict_b, floor: 71.29326283364946},
      strict_pair: {one_must_reach: 71.39843006187554, pass: $strict_pass}
    },
    evidence: {hardware_gate_pass: true, model_19_of_19_all_arms: true,
      exact_canary_all_arms: true, benchmark_shape_all_arms: true,
      strict_a_quality_battery_pass: true, cache_immutable_across_replays: true,
      cache_manifest_sha256: $cache_manifest_sha},
    preservation: {historical_values_lowered: 0, historical_values_replaced: 0,
      historical_overlay_applied: false}
  }' >"$result_root/result.json"
sha256sum "$result_root/result.json" | awk '{print $1}' >"$result_root/result.sha256"

if [[ $diagnostic_pass == true && $strict_pass == true ]]; then
  printf 'pass qualified=true\n' >"$result_root/final.status"
  failure_stage=complete
  exit 0
fi
printf 'complete qualified=false measured_speed_regression=true\n' >"$result_root/final.status"
failure_stage=complete-speed-regression
exit 10
