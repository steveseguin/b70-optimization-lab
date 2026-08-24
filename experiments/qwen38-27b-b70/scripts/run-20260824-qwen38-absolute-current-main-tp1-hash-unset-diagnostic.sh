#!/usr/bin/env bash
set -euo pipefail

# One diagnostic-only pre-campaign arm for the literal-current-main,
# both-current image. It preserves the historical hash-seed-unset performance
# identity without changing or satisfying the separate six-arm qualification.

script_path=$(realpath -e -- "${BASH_SOURCE[0]}")
script_dir=$(dirname -- "$script_path")
repo=$(git -C "$script_dir" rev-parse --show-toplevel)
runner=$script_dir/run-20260823-qwen38-absolute-current-main-strict-smoke.sh
receipt=$repo/experiments/qwen38-27b-b70/data/2026-08-23-qwen38-absolute-current-main-build.json
suite=$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json
model_manifest=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json
model_verifier=$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py
bench_helper=$repo/scripts/bench-openai-realistic-suite.py
quality_helper=$repo/scripts/qwen38-text-quality-suite.py
diagnostic_floor=30.2178
diagnostic_high=30.2569
stamp=${STAMP:-$(date -u +'%Y%m%dT%H%M%SZ')}
run_root=${RUN_ROOT:-/home/steve/qwen38-current-main-runs/tp1-hash-unset-$stamp}
out=$run_root/both-current-hash-unset-diagnostic
cache=$run_root/cache-both-current-hash-unset
port=${PORT:-19759}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

[[ -x $runner ]] || die "runner is not executable: $runner"
[[ -f $receipt ]] || die "missing build receipt: $receipt"
[[ -f $suite ]] || die "missing validation suite: $suite"
[[ ! -e $run_root ]] || die "run root already exists: $run_root"
[[ $port =~ ^[1-9][0-9]*$ && $port -le 65535 ]] || die 'invalid PORT'
for command_name in awk df env git grep jq realpath sha256sum; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done

run_root_parent=$(dirname -- "$run_root")
[[ -d $run_root_parent ]] || die "run-root parent is absent: $run_root_parent"
available_kib=$(df -Pk "$run_root_parent" | awk 'NR == 2 {print $4}')
[[ $available_kib =~ ^[0-9]+$ ]] || die 'could not read run filesystem free space'
(( available_kib >= 12 * 1024 * 1024 )) ||
  die 'diagnostic requires at least 12 GiB free on its ext4 filesystem'

mkdir -- "$run_root"

wrapper_cleanup() {
  local rc=$?
  local arm_status=
  trap - EXIT INT TERM HUP
  if [[ ! -f $run_root/final.status ]]; then
    [[ $rc -ne 0 ]] || rc=1
    if [[ -f $out/final.status ]]; then
      arm_status=$(<"$out/final.status")
    fi
    if [[ $arm_status == stale-before-promotion ]]; then
      printf 'stale-before-promotion arm=both-current-hash-unset-diagnostic rc=%s\n' \
        "$rc" >"$run_root/final.status"
    else
      printf 'fail rc=%s\n' "$rc" >"$run_root/final.status"
    fi
  fi
  exit "$rc"
}
trap wrapper_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

sha256sum "$script_path" "$runner" "$receipt" "$suite" \
  >"$run_root/input-files.sha256"

env -u PYTHONHASHSEED \
  CACHE_POLICY=fresh \
  PYTHONHASHSEED_MODE=unset \
  LAB_REPO_ROOT="$repo" \
  CURRENT_MAIN_BUILD_RECEIPT="$receipt" \
  CURRENT_MAIN_MODEL_MANIFEST="$model_manifest" \
  CURRENT_MAIN_MODEL_VERIFIER="$model_verifier" \
  CURRENT_MAIN_BENCH_HELPER="$bench_helper" \
  CURRENT_MAIN_QUALITY_HELPER="$quality_helper" \
  VLLM_XPU_GRAPH=1 \
  MAX_TOKENS=512 BENCH=1 CANARY=1 RETURN_TOKEN_IDS=1 \
  NATURAL_EOS=0 QUALITY=0 QUALITY_REQUIRE_BASELINE=0 \
    "$runner" both 0 f16 32768 0 "$port" "$out" "$suite" "$cache"

sha256sum -c "$run_root/input-files.sha256" >/dev/null ||
  die 'wrapper, runner, receipt, or suite changed during the diagnostic'
grep -qx 'pass' "$out/final.status" || die 'diagnostic runner did not pass'
for expected_identity in \
  lane=both \
  tp=1 \
  mtp=0 \
  cache_policy=fresh \
  natural_eos=0 \
  quality=0 \
  pythonhashseed_mode=unset \
  pythonhashseed_effective=unset; do
  grep -Fx "$expected_identity" "$out/identity.env" >/dev/null ||
    die "diagnostic identity is missing: $expected_identity"
done
grep -Fx 'requested_mode=unset' "$out/pythonhashseed-mode.env" >/dev/null ||
  die 'runner did not record hash-seed-unset mode'
grep -Fx 'container_variable_present=false' \
  "$out/pythonhashseed-mode.env" >/dev/null ||
  die 'PYTHONHASHSEED was present in the diagnostic container'
grep -Fx 'container_effective=unset' "$out/pythonhashseed-mode.env" >/dev/null ||
  die 'runner did not record an unset container hash seed'

jq -e '.summary.tok_s_1_100_intervals_after_ttft.median | numbers' \
  "$out/bench.json" >/dev/null || die 'diagnostic median is absent or nonnumeric'
actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
  "$out/bench.json")

jq -n \
  --arg run_root "$run_root" \
  --arg evidence "$out/bench.json" \
  --argjson actual "$actual" \
  --argjson floor "$diagnostic_floor" \
  --argjson high "$diagnostic_high" \
  --slurpfile build "$out/build-receipt.json" \
  '{
    schema: "neural-download-current-main-tp1-hash-unset-diagnostic-v1",
    classification: "diagnostic-only-pre-campaign-performance-preservation",
    strict_qualification: false,
    six_arm_campaign_satisfied: false,
    promotion_eligible: false,
    historical_replacement_allowed: false,
    run_root: $run_root,
    evidence: $evidence,
    identity: {
      lane: "both-current",
      tp: 1,
      mtp: 0,
      kv: "f16",
      max_model_len: 32768,
      pythonhashseed_mode: "unset",
      vllm_head: $build[0].vllm.head,
      kernel_head: $build[0].kernel.head,
      image_id: $build[0].images.both_current_zero_overlay.image_id
    },
    conventional_99_interval_median_tok_s: $actual,
    protected_comparison: {
      replicated_floor_tok_s: $floor,
      captured_high_tok_s: $high,
      floor_pass: ($actual >= $floor),
      high_is_gate: false,
      delta_from_floor_tok_s: ($actual - $floor),
      delta_from_captured_high_tok_s: ($actual - $high),
      percent_from_captured_high: ((($actual / $high) - 1) * 100)
    },
    history_policy: "Append this result as current-base evidence. Never lower, replace, or relabel the protected 30.2178 / 30.2569 captures.",
    next: (if $actual >= $floor
      then "The separate frozen six-arm seed-zero qualification may begin if all source identities remain current."
      else "Stop before the six-arm campaign and attribute the hash-seed-unset performance regression."
      end)
  }' >"$run_root/diagnostic-result.json"

if ! awk -v actual="$actual" -v floor="$diagnostic_floor" \
    'BEGIN { exit !(actual >= floor) }'; then
  printf 'fail-diagnostic-floor-miss actual=%s floor=%s high=%s\n' \
    "$actual" "$diagnostic_floor" "$diagnostic_high" >"$run_root/final.status"
  exit 6
fi

printf 'pass-diagnostic-only actual=%s floor=%s high=%s\n' \
  "$actual" "$diagnostic_floor" "$diagnostic_high" >"$run_root/final.status"
