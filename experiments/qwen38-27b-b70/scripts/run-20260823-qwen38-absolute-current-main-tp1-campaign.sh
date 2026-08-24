#!/usr/bin/env bash
set -euo pipefail

# Six-arm TP1 attribution/qualification campaign for the two immutable
# zero-overlay current-main images. It owns the host and GPU-0 leases for the
# complete sequence so another experiment cannot interleave between control
# and both-current measurements.

script_path=$(realpath -e -- "${BASH_SOURCE[0]}")
script_dir=$(dirname -- "$script_path")
repo=$(git -C "$script_dir" rev-parse --show-toplevel)
runner=$script_dir/run-20260823-qwen38-absolute-current-main-strict-smoke.sh
receipt=$repo/experiments/qwen38-27b-b70/data/2026-08-23-qwen38-absolute-current-main-build.json
suite=$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json
baseline=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json
model_manifest=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json
model_verifier=$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py
bench_helper=$repo/scripts/bench-openai-realistic-suite.py
quality_helper=$repo/scripts/qwen38-text-quality-suite.py
expected_suite_sha256=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
expected_baseline_sha256=738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18
diagnostic_floor=30.2178
strict_floor=30.31067504052998
stamp=${STAMP:-$(date -u +'%Y%m%dT%H%M%SZ')}
run_root=${RUN_ROOT:-/home/steve/qwen38-current-main-runs/tp1-$stamp}
port=${PORT:-19760}
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}
legacy_lock_file=/tmp/b70-benchmark.lock
muse_lock_file=/run/lock/muse-glimmer-gpu-exclusive.lock

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

dockerc() {
  sudo -S -p '' docker "$@" <"$sudo_pass_file"
}

container_id_present() {
  local target_id=$1 matches
  matches=$(dockerc ps -aq --no-trunc --filter "id=$target_id") || return 2
  [[ -z $matches ]] && return 1
  [[ $matches == "$target_id" ]] || return 2
  return 0
}

[[ -x $runner ]] || die "runner is not executable: $runner"
[[ -f $receipt ]] || die "missing build receipt: $receipt"
[[ -f $suite ]] || die "missing suite: $suite"
[[ -f $baseline ]] || die "missing quality baseline: $baseline"
[[ -f $model_manifest ]] || die "missing model manifest: $model_manifest"
[[ -x $model_verifier ]] || die "missing model verifier: $model_verifier"
[[ -f $bench_helper ]] || die "missing benchmark helper: $bench_helper"
[[ -f $quality_helper ]] || die "missing quality helper: $quality_helper"
[[ -r $sudo_pass_file ]] || die "sudo password file is unreadable: $sudo_pass_file"
for command_name in df find findmnt flock git jq realpath sha256sum; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done
[[ $(sha256sum "$suite" | awk '{print $1}') == "$expected_suite_sha256" ]] ||
  die 'validation suite hash changed'
[[ $(sha256sum "$baseline" | awk '{print $1}') == "$expected_baseline_sha256" ]] ||
  die 'quality baseline hash changed'
control_image_id=$(jq -r '.images.current_vllm_stock_kernel.image_id' "$receipt")
both_image_id=$(jq -r '.images.both_current_zero_overlay.image_id' "$receipt")
[[ $control_image_id =~ ^sha256:[0-9a-f]{64}$ ]] || die 'invalid control image ID'
[[ $both_image_id =~ ^sha256:[0-9a-f]{64}$ ]] || die 'invalid both-current image ID'
[[ ! -e $run_root ]] || die "run root already exists: $run_root"
[[ -z $(git -C "$repo" status --porcelain=v1 --untracked-files=all) ]] ||
  die 'lab repository must be completely clean'
[[ $(git -C "$repo" branch --show-current) == main ]] || die 'lab repository must be on main'
[[ $(git -C "$repo" rev-parse HEAD) == "$(git -C "$repo" rev-parse origin/main)" ]] ||
  die 'local main must equal origin/main'
live_lab_main=$(git -C "$repo" ls-remote --exit-code origin refs/heads/main |
  awk 'NR == 1 {print $1}')
[[ $live_lab_main =~ ^[0-9a-f]{40}$ ]] || die 'could not resolve live lab origin/main'
[[ $(git -C "$repo" rev-parse HEAD) == "$live_lab_main" ]] ||
  die 'local main must equal the live lab origin/main'
run_root_parent=$(dirname -- "$run_root")
[[ -d $run_root_parent ]] || die "campaign parent is absent: $run_root_parent"
available_kib=$(df -Pk "$run_root_parent" | awk 'NR == 2 {print $4}')
[[ $available_kib =~ ^[0-9]+$ ]] || die 'could not read campaign filesystem free space'
(( available_kib >= 12 * 1024 * 1024 )) ||
  die 'campaign requires at least 12 GiB free on its ext4 filesystem'

exec {muse_lock_fd}<>"$muse_lock_file"
flock -n "$muse_lock_fd" || die "Muse GPU lock is held: $muse_lock_file"
: >"$muse_lock_file"
printf 'qwen-current-main-campaign pid=%s runner=%s\n' "$$" "$script_path" \
  >&"$muse_lock_fd"
exec {host_lock_fd}<>"$legacy_lock_file"
flock -n "$host_lock_fd" || die "host benchmark lock is held: $legacy_lock_file"
: >"$legacy_lock_file"
printf 'qwen-current-main-campaign pid=%s runner=%s\n' "$$" "$script_path" \
  >&"$host_lock_fd"
gpu_lease_dir=/run/user/$(id -u)/qwen36-b70-gpu-leases
mkdir -p -- "$gpu_lease_dir"
gpu_lease_path=$gpu_lease_dir/gpu0.lock
exec {gpu_lease_fd}>"$gpu_lease_path"
flock -n "$gpu_lease_fd" || die 'GPU 0 is leased'
export QWEN_CURRENT_HOST_LOCK_FD=$host_lock_fd
export QWEN_CURRENT_MUSE_LOCK_FD=$muse_lock_fd
export QWEN_CURRENT_GPU_LEASE_FD=$gpu_lease_fd
export SUDO_PASS_FILE=$sudo_pass_file

mkdir -p -- "$run_root"
[[ $(findmnt -n -o FSTYPE --target "$run_root") == ext4 ]] ||
  die 'campaign root must be on ext4'

cleanup_recorded_containers() {
  local id_file container_id container_image_id state
  local found=0
  dockerc version >/dev/null 2>&1 || return 1
  while IFS= read -r -d '' id_file; do
    container_id=$(<"$id_file")
    [[ $container_id =~ ^[0-9a-f]{64}$ ]] || {
      printf 'invalid recorded container ID in %s\n' "$id_file" >&2
      found=1
      continue
    }
    if container_id_present "$container_id"; then
      found=1
      container_image_id=$(dockerc container inspect "$container_id" --format '{{.Image}}') ||
        continue
      case $container_image_id in
        "$control_image_id"|"$both_image_id") ;;
        *)
          printf 'refusing to remove recorded container with unexpected image ID: %s\n' \
            "$container_image_id" >&2
          continue
          ;;
      esac
      dockerc rm -f "$container_id" >/dev/null 2>&1 || continue
      if container_id_present "$container_id"; then
        printf 'recorded container survived ID-scoped cleanup: %s\n' \
          "$container_id" >&2
      else
        state=$?
        [[ $state -eq 1 ]] || printf 'could not confirm recorded container removal: %s\n' \
          "$container_id" >&2
      fi
    else
      state=$?
      if [[ $state -ne 1 ]]; then
        found=1
        printf 'could not determine recorded container state: %s\n' \
          "$container_id" >&2
      fi
    fi
  done < <(find "$run_root" -mindepth 2 -maxdepth 2 -type f \
    -name container-id.txt -print0 2>/dev/null)
  for container_name in \
    qwen38-absolute-current-main-control-$port \
    qwen38-absolute-current-main-both-$port; do
    if dockerc container inspect "$container_name" >/dev/null 2>&1; then
      found=1
      printf 'campaign container still exists after recorded-ID cleanup: %s\n' \
        "$container_name" >&2
    fi
  done
  [[ $found == 0 ]]
}

campaign_cleanup() {
  local rc=$?
  local cleanup_failed=0
  trap - EXIT INT TERM HUP
  cleanup_recorded_containers || cleanup_failed=1
  if [[ $cleanup_failed == 1 ]]; then
    printf 'fail-cleanup body_rc=%s\n' "$rc" >"$run_root/final.status"
    exit 7
  fi
  if [[ ! -f $run_root/final.status ]]; then
    [[ $rc -ne 0 ]] || rc=1
    printf 'fail rc=%s\n' "$rc" >"$run_root/final.status"
  fi
  exit "$rc"
}
trap campaign_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

input_dir=$run_root/inputs
mkdir -- "$input_dir"
cp -- "$receipt" "$input_dir/build-receipt.json"
cp -- "$suite" "$input_dir/validation-suite.json"
cp -- "$baseline" "$input_dir/quality-baseline.json"
cp -- "$runner" "$input_dir/strict-smoke.sh"
cp -- "$model_manifest" "$input_dir/model-manifest.json"
cp -- "$model_verifier" "$input_dir/verify-model-direct.py"
cp -- "$bench_helper" "$input_dir/bench-openai-realistic-suite.py"
cp -- "$quality_helper" "$input_dir/qwen38-text-quality-suite.py"
cp -- "$script_path" "$input_dir/tp1-campaign.sh"
[[ $(sha256sum "$input_dir/validation-suite.json" | awk '{print $1}') == \
   "$expected_suite_sha256" ]] || die 'frozen validation suite hash changed during copy'
[[ $(sha256sum "$input_dir/quality-baseline.json" | awk '{print $1}') == \
   "$expected_baseline_sha256" ]] || die 'frozen quality baseline hash changed during copy'
chmod 0444 "$input_dir"/*.json "$input_dir"/*.py "$input_dir/tp1-campaign.sh"
chmod 0555 "$input_dir/strict-smoke.sh" "$input_dir/verify-model-direct.py"
(
  cd "$input_dir"
  sha256sum build-receipt.json validation-suite.json quality-baseline.json \
    strict-smoke.sh model-manifest.json verify-model-direct.py \
    bench-openai-realistic-suite.py qwen38-text-quality-suite.py \
    tp1-campaign.sh >SHA256SUMS
)
chmod 0444 "$input_dir/SHA256SUMS"

frozen_receipt=$input_dir/build-receipt.json
frozen_suite=$input_dir/validation-suite.json
frozen_baseline=$input_dir/quality-baseline.json
frozen_runner=$input_dir/strict-smoke.sh
frozen_model_manifest=$input_dir/model-manifest.json
frozen_model_verifier=$input_dir/verify-model-direct.py
frozen_bench_helper=$input_dir/bench-openai-realistic-suite.py
frozen_quality_helper=$input_dir/qwen38-text-quality-suite.py

check_frozen_inputs() {
  (cd "$input_dir" && sha256sum -c SHA256SUMS >/dev/null)
}
check_frozen_inputs || die 'campaign input snapshot failed its initial seal'
cp -- "$frozen_receipt" "$run_root/build-receipt.json"
cp -- "$frozen_suite" "$run_root/validation-suite.json"
cp -- "$input_dir/SHA256SUMS" "$run_root/input-files.sha256"

campaign_vllm_head=$(jq -r .vllm.head "$frozen_receipt")
campaign_kernel_head=$(jq -r .kernel.head "$frozen_receipt")
campaign_base_digest=$(jq -r .base_digest "$frozen_receipt")
control_kernel_version=0.1.13.2
remote_vllm_pre=$(git ls-remote --exit-code https://github.com/vllm-project/vllm.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_kernel_pre=$(git ls-remote --exit-code https://github.com/vllm-project/vllm-xpu-kernels.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_base_pre=$(dockerc buildx imagetools inspect vllm/vllm-openai-xpu:nightly \
  --format '{{.Manifest.Digest}}')
printf '%s\n' "$remote_vllm_pre" >"$run_root/upstream-vllm.pre.txt"
printf '%s\n' "$remote_kernel_pre" >"$run_root/upstream-kernel.pre.txt"
printf '%s\n' "$remote_base_pre" >"$run_root/upstream-nightly-base.pre.txt"
[[ $remote_vllm_pre == "$campaign_vllm_head" ]] ||
  die 'vLLM main advanced; rebuild instead of qualifying a stale image'
[[ $remote_kernel_pre == "$campaign_kernel_head" ]] ||
  die 'XPU-kernel main advanced; rebuild instead of qualifying a stale image'
[[ $remote_base_pre == "$campaign_base_digest" ]] ||
  die 'official nightly base advanced; rebuild instead of qualifying a stale image'

run_lane() {
  local lane=$1
  local cache=$run_root/cache-$lane
  local diagnostic=$run_root/$lane-diagnostic-fresh
  local strict_a=$run_root/$lane-strict-replay-a
  local strict_b=$run_root/$lane-strict-replay-b
  local manifest_sha

  check_frozen_inputs || die "$lane inputs changed before diagnostic"
  CACHE_POLICY=fresh \
  LAB_REPO_ROOT=$repo \
  CURRENT_MAIN_BUILD_RECEIPT=$frozen_receipt \
  CURRENT_MAIN_MODEL_MANIFEST=$frozen_model_manifest \
  CURRENT_MAIN_MODEL_VERIFIER=$frozen_model_verifier \
  CURRENT_MAIN_BENCH_HELPER=$frozen_bench_helper \
  CURRENT_MAIN_QUALITY_HELPER=$frozen_quality_helper \
  VLLM_XPU_GRAPH=1 PYTHONHASHSEED=0 \
  MAX_TOKENS=512 BENCH=1 CANARY=1 RETURN_TOKEN_IDS=1 \
  NATURAL_EOS=0 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$frozen_runner" "$lane" 0 f16 32768 0 "$port" \
      "$diagnostic" "$frozen_suite" "$cache"
  check_frozen_inputs || die "$lane inputs changed during diagnostic"

  manifest_sha=$(awk 'NR == 1 {print $1}' \
    "$diagnostic/cache-manifest.post.sha256.digest")
  [[ $manifest_sha =~ ^[0-9a-f]{64}$ ]] || die "$lane produced an invalid cache manifest"
  [[ $manifest_sha == "$(sha256sum "$diagnostic/cache-manifest.post.sha256" |
    awk '{print $1}')" ]] || die "$lane cache-manifest digest does not match its file"

  check_frozen_inputs || die "$lane inputs changed before strict replay A"
  CACHE_POLICY=replay EXPECTED_CACHE_MANIFEST_SHA256=$manifest_sha \
  LAB_REPO_ROOT=$repo \
  CURRENT_MAIN_BUILD_RECEIPT=$frozen_receipt \
  CURRENT_MAIN_MODEL_MANIFEST=$frozen_model_manifest \
  CURRENT_MAIN_MODEL_VERIFIER=$frozen_model_verifier \
  CURRENT_MAIN_BENCH_HELPER=$frozen_bench_helper \
  CURRENT_MAIN_QUALITY_HELPER=$frozen_quality_helper \
  VLLM_XPU_GRAPH=1 PYTHONHASHSEED=0 \
  MAX_TOKENS=512 BENCH=1 CANARY=1 RETURN_TOKEN_IDS=1 \
  NATURAL_EOS=1 QUALITY=1 QUALITY_REQUIRE_BASELINE=1 \
  QUALITY_BASELINE_JSON=$frozen_baseline \
    "$frozen_runner" "$lane" 0 f16 32768 0 "$port" \
      "$strict_a" "$frozen_suite" "$cache"
  check_frozen_inputs || die "$lane inputs changed during strict replay A"

  check_frozen_inputs || die "$lane inputs changed before strict replay B"
  CACHE_POLICY=replay EXPECTED_CACHE_MANIFEST_SHA256=$manifest_sha \
  LAB_REPO_ROOT=$repo \
  CURRENT_MAIN_BUILD_RECEIPT=$frozen_receipt \
  CURRENT_MAIN_MODEL_MANIFEST=$frozen_model_manifest \
  CURRENT_MAIN_MODEL_VERIFIER=$frozen_model_verifier \
  CURRENT_MAIN_BENCH_HELPER=$frozen_bench_helper \
  CURRENT_MAIN_QUALITY_HELPER=$frozen_quality_helper \
  VLLM_XPU_GRAPH=1 PYTHONHASHSEED=0 \
  MAX_TOKENS=512 BENCH=1 CANARY=1 RETURN_TOKEN_IDS=1 \
  NATURAL_EOS=1 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$frozen_runner" "$lane" 0 f16 32768 0 "$port" \
      "$strict_b" "$frozen_suite" "$cache"
  check_frozen_inputs || die "$lane inputs changed during strict replay B"

  cmp -s "$diagnostic/cache-manifest.post.sha256" "$strict_a/cache-manifest.pre.sha256" ||
    die "$lane strict replay A did not use the diagnostic cache"
  cmp -s "$strict_a/cache-manifest.pre.sha256" "$strict_a/cache-manifest.post.sha256" ||
    die "$lane strict replay A mutated its cache"
  cmp -s "$strict_a/cache-manifest.pre.sha256" "$strict_b/cache-manifest.pre.sha256" ||
    die "$lane strict replay B did not use the same sealed cache"
  cmp -s "$strict_b/cache-manifest.pre.sha256" "$strict_b/cache-manifest.post.sha256" ||
    die "$lane strict replay B mutated its cache"

  jq -n \
    --arg lane "$lane" \
    --arg diagnostic "$diagnostic/bench.json" \
    --arg strict_a "$strict_a/bench.json" \
    --arg strict_b "$strict_b/bench.json" \
    --argjson diagnostic_floor "$diagnostic_floor" \
    --argjson strict_floor "$strict_floor" \
    --slurpfile d "$diagnostic/bench.json" \
    --slurpfile a "$strict_a/bench.json" \
    --slurpfile b "$strict_b/bench.json" \
    --slurpfile q "$strict_a/quality.json" \
    '($d[0]) as $d0 | ($a[0]) as $a0 | ($b[0]) as $b0 | ($q[0]) as $q0 |
    [range(0; ($a0.rows | length)) as $i | {
      prompt_id: $a0.rows[$i].prompt_id,
      prompt_id_matches: ($a0.rows[$i].prompt_id == $b0.rows[$i].prompt_id),
      full_token_ids_equal: ($a0.rows[$i].token_ids == $b0.rows[$i].token_ids),
      first_100_token_ids_equal: ($a0.rows[$i].token_ids[:100] == $b0.rows[$i].token_ids[:100])
    }] as $pairs | {
      schema: "neural-download-current-main-tp1-lane-v1",
      lane: $lane,
      evidence: {diagnostic: $diagnostic, strict_a: $strict_a, strict_b: $strict_b},
      floors_tok_s: {diagnostic: $diagnostic_floor, strict: $strict_floor},
      conventional_99_interval_medians_tok_s: {
        diagnostic: $d0.summary.tok_s_1_100_intervals_after_ttft.median,
        strict_a: $a0.summary.tok_s_1_100_intervals_after_ttft.median,
        strict_b: $b0.summary.tok_s_1_100_intervals_after_ttft.median
      },
      speed_gates: {
        diagnostic: ($d0.summary.tok_s_1_100_intervals_after_ttft.median >= $diagnostic_floor),
        strict_a: ($a0.summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor),
        strict_b: ($b0.summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor)
      },
      replay_token_comparison: {
        prompt_count: ($pairs | length),
        prompt_order_matches: (all($pairs[]; .prompt_id_matches)),
        full_token_array_matches: ([$pairs[] | select(.full_token_ids_equal)] | length),
        first_100_token_array_matches: ([$pairs[] | select(.first_100_token_ids_equal)] | length),
        rows: $pairs
      },
      quality_a: {
        pass_all: $q0.pass_all,
        baseline_match_all: $q0.baseline_match_all,
        exact_cases: ($q0.exact_cases | length),
        repeat_runs: ($q0.repeat_case.runs | length),
        long_context_tokens: $q0.long_context_case.requested_context_tokens,
        long_context_actual_prompt_tokens: $q0.long_context_case.actual_prompt_tokens,
        baseline_comparisons: ($q0.baseline_comparisons | length),
        cached_tokens_all_zero: (
          all($q0.exact_cases[]; .usage.prompt_tokens_details.cached_tokens == 0) and
          all($q0.repeat_case.runs[]; .usage.prompt_tokens_details.cached_tokens == 0) and
          $q0.long_context_case.usage.prompt_tokens_details.cached_tokens == 0
        )
      },
      quality_gates_pass: (
        $q0.pass_all == true and $q0.baseline_match_all == true and
        ($q0.exact_cases | length) == 7 and
        ($q0.repeat_case.runs | length) == 8 and
        $q0.long_context_case.requested_context_tokens == 8192 and
        $q0.long_context_case.actual_prompt_tokens == 7617 and
        ($q0.baseline_comparisons | length) == 24 and
        all($q0.exact_cases[]; .usage.prompt_tokens_details.cached_tokens == 0) and
        all($q0.repeat_case.runs[]; .usage.prompt_tokens_details.cached_tokens == 0) and
        $q0.long_context_case.usage.prompt_tokens_details.cached_tokens == 0
      ),
      benchmark_shape_gates_pass: (
        ($d0.rows | length) == 25 and ($a0.rows | length) == 25 and
        ($b0.rows | length) == 25 and all($pairs[]; .prompt_id_matches)
      ),
      all_speed_gates_pass: (
        $d0.summary.tok_s_1_100_intervals_after_ttft.median >= $diagnostic_floor and
        $a0.summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor and
        $b0.summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor
      ),
      all_qualification_gates_pass: (
        $d0.summary.tok_s_1_100_intervals_after_ttft.median >= $diagnostic_floor and
        $a0.summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor and
        $b0.summary.tok_s_1_100_intervals_after_ttft.median >= $strict_floor and
        ($d0.rows | length) == 25 and ($a0.rows | length) == 25 and
        ($b0.rows | length) == 25 and all($pairs[]; .prompt_id_matches) and
        $q0.pass_all == true and $q0.baseline_match_all == true and
        ($q0.exact_cases | length) == 7 and
        ($q0.repeat_case.runs | length) == 8 and
        $q0.long_context_case.requested_context_tokens == 8192 and
        $q0.long_context_case.actual_prompt_tokens == 7617 and
        ($q0.baseline_comparisons | length) == 24 and
        all($q0.exact_cases[]; .usage.prompt_tokens_details.cached_tokens == 0) and
        all($q0.repeat_case.runs[]; .usage.prompt_tokens_details.cached_tokens == 0) and
        $q0.long_context_case.usage.prompt_tokens_details.cached_tokens == 0
      )
    }' >"$run_root/$lane-result.json"
}

run_lane control
run_lane both
check_frozen_inputs || die 'campaign input snapshot changed after the final arm'

remote_vllm_post=$(git ls-remote --exit-code https://github.com/vllm-project/vllm.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_kernel_post=$(git ls-remote --exit-code https://github.com/vllm-project/vllm-xpu-kernels.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_base_post=$(dockerc buildx imagetools inspect vllm/vllm-openai-xpu:nightly \
  --format '{{.Manifest.Digest}}')
printf '%s\n' "$remote_vllm_post" >"$run_root/upstream-vllm.post.txt"
printf '%s\n' "$remote_kernel_post" >"$run_root/upstream-kernel.post.txt"
printf '%s\n' "$remote_base_post" >"$run_root/upstream-nightly-base.post.txt"
upstream_unchanged=false
if [[ $remote_vllm_post == "$campaign_vllm_head" &&
      $remote_kernel_post == "$campaign_kernel_head" &&
      $remote_base_post == "$campaign_base_digest" ]]; then
  upstream_unchanged=true
fi
live_lab_main_post=$(git -C "$repo" ls-remote --exit-code origin refs/heads/main |
  awk 'NR == 1 {print $1}')
lab_unchanged=false
if [[ $live_lab_main_post == "$live_lab_main" &&
      $(git -C "$repo" rev-parse HEAD) == "$live_lab_main_post" &&
      -z $(git -C "$repo" status --porcelain=v1 --untracked-files=all) ]]; then
  lab_unchanged=true
fi

jq -n \
  --slurpfile control "$run_root/control-result.json" \
  --slurpfile both "$run_root/both-result.json" \
  --arg run_root "$run_root" \
  --arg vllm_head "$campaign_vllm_head" \
  --arg kernel_head "$campaign_kernel_head" \
  --arg base_digest "$campaign_base_digest" \
  --arg control_kernel_version "$control_kernel_version" \
  --argjson upstream_unchanged "$upstream_unchanged" \
  --argjson lab_unchanged "$lab_unchanged" \
  '{
    schema: "neural-download-current-main-tp1-campaign-v1",
    state: (if ($upstream_unchanged and $lab_unchanged)
      then "complete" else "stale-before-promotion" end),
    run_root: $run_root,
    source: {
      vllm_head: $vllm_head,
      official_nightly_base_digest: $base_digest,
      control_kernel: {identity: "stock-from-base", version: $control_kernel_version},
      both_current_kernel: {head: $kernel_head},
      upstream_unchanged: $upstream_unchanged,
      lab_unchanged: $lab_unchanged
    },
    protected_history: {
      diagnostic_floor_tp1_tok_s: 30.2178,
      strict_floor_tp1_tok_s: 30.31067504052998,
      diagnostic_floor_origin_pythonhashseed: "unset",
      strict_floor_origin_pythonhashseed: 0,
      current_campaign_pythonhashseed: 0,
      comparison_scope: "The diagnostic value is a protected speed floor, not an exact hash-seed identity replay.",
      rule: "A slower current result is diagnostic evidence and never replaces the certified historical high."
    },
    interpretation: {
      active_candidate: "both-current",
      control_role: "Coarse current-vLLM/stock-kernel comparison against current-vLLM/current-kernel.",
      kernel_delta_scope: "Independent fresh autotune realizations and fixed control-first order make a small control/both speed delta inconclusive for kernel causality.",
      advance_rule: "Only both-current must clear every speed, shape, quality, cache, and source-recency gate; a slower control does not veto a qualified current-kernel stack."
    },
    control: $control[0],
    both_current: $both[0],
    control_speed_ready: $control[0].all_speed_gates_pass,
    both_current_speed_ready: (
      $both[0].all_speed_gates_pass and $upstream_unchanged and $lab_unchanged
    ),
    both_current_qualification_ready: (
      $both[0].all_qualification_gates_pass and $upstream_unchanged and $lab_unchanged
    ),
    next: (if ($both[0].all_qualification_gates_pass and
      $upstream_unchanged and $lab_unchanged)
      then "preserve the zero-source-overlay result, remap accepted launch/autotune overlays, then qualify TP2"
      else "do not advance; attribute the regression and forward-port the missing accepted behavior"
      end)
  }' >"$run_root/campaign-result.json"

if [[ $upstream_unchanged != true || $lab_unchanged != true ]]; then
  printf 'stale-before-promotion\n' >"$run_root/final.status"
  exit 5
fi
if [[ $(jq -r .both_current_qualification_ready "$run_root/campaign-result.json") != true ]]; then
  printf 'complete-regression-attribution-required\n' >"$run_root/final.status"
  exit 6
fi
printf 'pass\n' >"$run_root/final.status"
