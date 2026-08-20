#!/usr/bin/env bash
set -euo pipefail

# Full-history causal screen for the rank-local model-forward completion
# boundary. S1 is compared report-only with sane B2. S2 is authorized only if
# S1's prompt 24 is sane and then requires complete S2/S1 token parity.

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
driver=$(realpath -- "$0")
action=${1:-}
s1_checksum_manifest_expected=${2:-}

if [[ "$action" != "check" && "$action" != "s1" && "$action" != "s2" ]] \
  || { [[ "$action" == "s2" ]] \
    && [[ ! "$s1_checksum_manifest_expected" =~ ^[0-9a-f]{64}$ ]]; }; then
  printf 'usage: %s check|s1|s2 S1_CHECKSUM_MANIFEST_SHA256\n' "$0" >&2
  exit 2
fi

raw=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70
c1="$raw/qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-c1-20260820"
b2="$raw/qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-b2-20260820"
s1_label=qwen38-detpad-composite4dd-marginfree-mtp5-25-postforward-sync-s1-20260820
s2_label=qwen38-detpad-composite4dd-marginfree-mtp5-25-postforward-sync-s2-20260820
s1="$raw/$s1_label"
s2="$raw/$s2_label"
base_env="$c1/run/validation-input.env"
runner="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh"
quality_baseline="$raw/qwen38-marginfree-targetoracle-25-a-20260820/data/quality.json"
cache=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820
cache_manifest="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-c-20260820/compile-cache-output-manifest.json"

c1_checksum_manifest_sha=4037f0fee4ada9e47eab90bd560986724be589d6facf96890cf2bff8b93acc49
c1_validation_env_sha=eb5200a03802b1f193beb04a07d260efe1c39f71edc96b31ba866d313b4ec0eb
c1_bench_sha=8ff7a2e9ce7c41997e41747c1a35b71b8a06d0920030ecdc71d3305e7c08408e
b2_bench_sha=96933a8211867479410375aaad7bd96bfb9f97d0edafc12af80dc9963805e721
cache_manifest_sha=f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff
quality_sha=45424f1d2dcbfda0a5ed75552cf799cac0e8fb6b8c5e1ddf2aba540b95c77e95

verify_sha() {
  local path=$1 expected=$2 description=$3 actual
  if [[ ! -f "$path" ]]; then
    printf '%s is missing: %s\n' "$description" "$path" >&2
    exit 3
  fi
  actual=$(sha256sum -- "$path" | awk '{print $1}')
  if [[ "$actual" != "$expected" ]]; then
    printf '%s SHA mismatch: actual=%s expected=%s\n' \
      "$description" "$actual" "$expected" >&2
    exit 3
  fi
}

if [[ "$(git -C "$repo" branch --show-current)" != "main" ]]; then
  printf 'post-forward-sync launcher requires main\n' >&2
  exit 3
fi
if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]]; then
  printf 'post-forward-sync launcher requires a clean repository\n' >&2
  exit 3
fi
if [[ "$(git -C "$repo" rev-parse HEAD)" \
  != "$(git -C "$repo" rev-parse origin/main)" ]]; then
  printf 'post-forward-sync launcher requires local main == origin/main\n' >&2
  exit 3
fi

verify_sha "$c1/SHA256SUMS.pre-manifest" \
  "$c1_checksum_manifest_sha" c1-checksum-manifest
if ! (cd "$c1" && sha256sum -c SHA256SUMS.pre-manifest >/dev/null); then
  printf 'C1 checksum set no longer verifies\n' >&2
  exit 3
fi
verify_sha "$base_env" "$c1_validation_env_sha" c1-validation-environment
verify_sha "$c1/data/bench.json" "$c1_bench_sha" c1-benchmark
verify_sha "$b2/data/bench.json" "$b2_bench_sha" sane-b2-benchmark
verify_sha "$cache_manifest" "$cache_manifest_sha" sealed-cache-manifest
verify_sha "$quality_baseline" "$quality_sha" quality-baseline
if [[ "$(tr -d '\n' < "$c1/runner.exit-code")" != "14" ]] \
  || ! jq -e '.status == "passed" and (.errors | length == 0)' \
    "$c1/tp2-sealed-gates.json" >/dev/null \
  || ! jq -e '.schema == "qwen38-token-array-parity-v1" \
      and .status == "failed" \
      and .candidate_peer.exact_count == 22 \
      and .candidate_reference.exact_count == 23' \
    "$c1/token-parity.json" >/dev/null; then
  printf 'C1 no longer proves the preregistered active recurrence\n' >&2
  exit 3
fi
"$repo/scripts/canonical-tree-manifest.py" verify \
  --root "$cache/torch_compile_cache" --manifest "$cache_manifest" >/dev/null

if [[ "$action" == "check" ]]; then
  printf 'sealed post-forward-sync preflight passed\n'
  exit 0
fi

if [[ "$action" == "s1" ]]; then
  label=$s1_label
  arm_root=$s1
  peer_bench=
  peer_sha=
else
  label=$s2_label
  arm_root=$s2
  peer_bench="$s1/data/bench.json"
  verify_sha "$s1/SHA256SUMS.pre-manifest" \
    "$s1_checksum_manifest_expected" s1-checksum-manifest
  if [[ ! -f "$s1/runner.exit-code" \
    || "$(tr -d '\n' < "$s1/runner.exit-code")" != "0" \
    || ! -f "$peer_bench" \
    || ! -f "$s1/SHA256SUMS.pre-manifest" ]] \
    || ! (cd "$s1" && sha256sum -c SHA256SUMS.pre-manifest >/dev/null); then
    printf 'S1 did not complete its sealed arm gate\n' >&2
    exit 4
  fi
  if ! jq -e '.status == "passed" and (.errors | length == 0)' \
    "$s1/tp2-sealed-gates.json" >/dev/null; then
    printf 'S1 no longer passes its sealed arm gate\n' >&2
    exit 4
  fi
  s1_bench_sha=$(jq -r '.benchmark.sha256 // empty' \
    "$s1/tp2-sealed-gates.json")
  if [[ ! "$s1_bench_sha" =~ ^[0-9a-f]{64}$ \
    || "$(sha256sum -- "$peer_bench" | awk '{print $1}')" != "$s1_bench_sha" \
    || "$(tr -d '\n' < "$s1/run/llm-optimizations.git-head")" \
      != "$(git -C "$repo" rev-parse HEAD)" \
    || "$(awk -F= '$1 == "campaign_driver_sha256" {print $2}' \
        "$s1/run/identity.env")" != "$(sha256sum -- "$driver" | awk '{print $1}')" \
    || "$(awk -F= '$1 == "sync_after_model_forward" {print $2}' \
        "$s1/run/identity.env")" != "1" \
    || "$(awk -F= '$1 == "expected_sync_after_model_forward" {print $2}' \
        "$s1/run/identity.env")" != "1" ]]; then
    printf 'S1 is not bound to the current synchronized campaign identity\n' >&2
    exit 4
  fi
  if ! jq -e --slurpfile b2 "$b2/data/bench.json" \
    '.rows[24].prompt_id == "holdout--long-rollover-repository-audit" \
      and .rows[24].token_ids == $b2[0].rows[24].token_ids' \
    "$peer_bench" >/dev/null; then
    printf 'S1 prompt 24 is not the sane B2 token family; S2 is forbidden\n' >&2
    exit 4
  fi
  peer_sha=$s1_bench_sha
fi

if [[ -e "$arm_root" ]]; then
  printf 'refusing existing sync arm root: %s\n' "$arm_root" >&2
  exit 4
fi

declare -a launch_env=()
while IFS= read -r assignment; do
  if [[ ! "$assignment" =~ ^[A-Z][A-Z0-9_]*= ]]; then
    printf 'malformed frozen environment assignment: %s\n' "$assignment" >&2
    exit 3
  fi
  name=${assignment%%=*}
  case "$name" in
    VALIDATION_CAMPAIGN_DRIVER|VALIDATION_CAMPAIGN_DRIVER_SHA256|\
    VALIDATION_EXPECT_REPO_HEAD|VALIDATION_PARITY_PEER_BENCH|\
    VALIDATION_EXPECT_PARITY_PEER_BENCH_SHA256|VALIDATION_TARGET_TOKEN_BENCH|\
    VALIDATION_EXPECT_TARGET_TOKEN_BENCH_SHA256|\
    VALIDATION_EXPECT_PARITY_PEER_CHECKSUM_MANIFEST_SHA256|\
    VALIDATION_SYNC_AFTER_MODEL_FORWARD|\
    VALIDATION_EXPECT_SYNC_AFTER_MODEL_FORWARD)
      ;;
    *)
      launch_env+=("$assignment")
      ;;
  esac
done < "$base_env"

repo_head=$(git -C "$repo" rev-parse HEAD)
driver_sha=$(sha256sum -- "$driver" | awk '{print $1}')
launch_env+=(
  "VALIDATION_CAMPAIGN_DRIVER=$driver"
  "VALIDATION_CAMPAIGN_DRIVER_SHA256=$driver_sha"
  "VALIDATION_EXPECT_REPO_HEAD=$repo_head"
  VALIDATION_SYNC_AFTER_MODEL_FORWARD=1
  VALIDATION_EXPECT_SYNC_AFTER_MODEL_FORWARD=1
  "VALIDATION_TARGET_TOKEN_BENCH=$b2/data/bench.json"
  "VALIDATION_EXPECT_TARGET_TOKEN_BENCH_SHA256=$b2_bench_sha"
)
if [[ -n "$peer_bench" ]]; then
  launch_env+=(
    "VALIDATION_PARITY_PEER_BENCH=$peer_bench"
    "VALIDATION_EXPECT_PARITY_PEER_BENCH_SHA256=$peer_sha"
    "VALIDATION_EXPECT_PARITY_PEER_CHECKSUM_MANIFEST_SHA256=$s1_checksum_manifest_expected"
  )
fi

env -i HOME=/home/steve USER=steve LOGNAME=steve SHELL=/bin/bash \
  LANG=C.UTF-8 PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  "LABEL=$label" "${launch_env[@]}" \
  "$runner" spec-native-partition-exact-native 2,3 "$arm_root" \
  "$quality_baseline"
