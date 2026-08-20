#!/usr/bin/env bash
set -euo pipefail

# One-arm, full-history prompt-24 replay microscope. This is intentionally
# perturbative and diagnostic-only; no repeat or performance promotion is
# authorized by this driver.

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
driver=$(realpath -- "$0")
action=${1:-}

if [[ "$action" != "check" && "$action" != "m1" ]]; then
  printf 'usage: %s check|m1\n' "$0" >&2
  exit 2
fi
if [[ "$action" == "m1" ]]; then
  printf 'M1 is permanently closed; preserve the original arm and do not retry\n' >&2
  exit 4
fi

raw=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70
c1="$raw/qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-c1-20260820"
b2="$raw/qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-b2-20260820"
label=qwen38-detpad-composite4dd-marginfree-mtp5-25-replay-microscope-m1-20260820
arm_root="$raw/$label"
base_env="$c1/run/validation-input.env"
runner="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh"
quality_baseline="$raw/qwen38-marginfree-targetoracle-25-a-20260820/data/quality.json"
cache=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820
cache_manifest="$raw/qwen38-postrecovery-marginfree-mtp5-25-spec-c-20260820/compile-cache-output-manifest.json"
trace="$arm_root/replay-microscope.jsonl"
request_regex='^chatcmpl-bench-qwen36-27b-int4-independent-validation-20260815-v1-24-holdout--long-rollover-repository-audit$'

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
  printf 'replay-microscope launcher requires main\n' >&2
  exit 3
fi
if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]]; then
  printf 'replay-microscope launcher requires a clean repository\n' >&2
  exit 3
fi
if [[ "$(git -C "$repo" rev-parse HEAD)" \
  != "$(git -C "$repo" rev-parse origin/main)" ]]; then
  printf 'replay-microscope launcher requires local main == origin/main\n' >&2
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
  || ! jq -e '.schema == "qwen38-token-array-parity-v1"
      and .status == "failed"
      and .candidate_peer.exact_count == 22
      and .candidate_reference.exact_count == 23' \
    "$c1/token-parity.json" >/dev/null; then
  printf 'C1 no longer proves the preregistered active recurrence\n' >&2
  exit 3
fi
"$repo/scripts/canonical-tree-manifest.py" verify \
  --root "$cache/torch_compile_cache" --manifest "$cache_manifest" >/dev/null

if [[ "$action" == "check" ]]; then
  if [[ -e "$arm_root" ]]; then
    printf 'microscope arm root already exists: %s\n' "$arm_root" >&2
    exit 4
  fi
  printf 'sealed replay-microscope preflight passed\n'
  exit 0
fi

if [[ -e "$arm_root" ]]; then
  printf 'refusing existing microscope arm root: %s\n' "$arm_root" >&2
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
    VALIDATION_EXPECT_SYNC_AFTER_MODEL_FORWARD|\
    VALIDATION_REQUIRE_REPLAY_MICROSCOPE|VALIDATION_REPLAY_MICROSCOPE_FILE|\
    VALIDATION_REPLAY_MICROSCOPE_MAX_LINES|VALIDATION_REPLAY_MICROSCOPE_RANK|\
    VALIDATION_REPLAY_MICROSCOPE_REQ_REGEX|\
    VALIDATION_REPLAY_MICROSCOPE_TENSOR_LIMIT|\
    VALIDATION_REPLAY_MICROSCOPE_TOPK|\
    VALIDATION_REPLAY_MICROSCOPE_MIN_TOKENS_NO_SPEC|\
    VALIDATION_REPLAY_MICROSCOPE_MAX_TOKENS_NO_SPEC)
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
  VALIDATION_SYNC_AFTER_MODEL_FORWARD=0
  VALIDATION_EXPECT_SYNC_AFTER_MODEL_FORWARD=0
  VALIDATION_REQUIRE_REPLAY_MICROSCOPE=1
  "VALIDATION_REPLAY_MICROSCOPE_FILE=$trace"
  VALIDATION_REPLAY_MICROSCOPE_MAX_LINES=6
  VALIDATION_REPLAY_MICROSCOPE_RANK=0
  "VALIDATION_REPLAY_MICROSCOPE_REQ_REGEX=$request_regex"
  VALIDATION_REPLAY_MICROSCOPE_TENSOR_LIMIT=1
  VALIDATION_REPLAY_MICROSCOPE_TOPK=0
  VALIDATION_REPLAY_MICROSCOPE_MIN_TOKENS_NO_SPEC=849
  VALIDATION_REPLAY_MICROSCOPE_MAX_TOKENS_NO_SPEC=849
  "VALIDATION_TARGET_TOKEN_BENCH=$b2/data/bench.json"
  "VALIDATION_EXPECT_TARGET_TOKEN_BENCH_SHA256=$b2_bench_sha"
)

env -i HOME=/home/steve USER=steve LOGNAME=steve SHELL=/bin/bash \
  LANG=C.UTF-8 PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  "LABEL=$label" "${launch_env[@]}" \
  "$runner" spec-native-partition-exact-native 2,3 "$arm_root" \
  "$quality_baseline"
