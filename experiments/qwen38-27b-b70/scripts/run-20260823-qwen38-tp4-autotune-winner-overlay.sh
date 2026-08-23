#!/usr/bin/env bash
set -euo pipefail

mode=${1:?usage: $0 fresh|replay-a|replay-b}
[[ "$mode" == "fresh" || "$mode" == "replay-a" || \
   "$mode" == "replay-b" ]] || {
  echo "error: mode must be fresh, replay-a, or replay-b" >&2
  exit 2
}

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
runner="$repo/experiments/qwen38-27b-b70/scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh"
suite="$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json"
overlay="$repo/experiments/qwen38-27b-b70/autotune-winner-overlays/tp4-e9d1398-best-config"
seed="$overlay/source"
result_root=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/rolling-nightly-a3561ef8e
fresh_out="$result_root/tp4-graph-autotune-winner-seeded-fresh"
replay_a_out="$result_root/tp4-graph-autotune-winner-strict-quality-replay-a"
replay_b_out="$result_root/tp4-graph-autotune-winner-strict-replay-b"
cache=/mnt/fast-ai/runtime/qwen38-rolling-a3561ef8e/tp4-autotune-winner-cache
baseline=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp4-mtp0-f16-graph-natural-eos-replay-a-baseline-quality/quality.json
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}

image_digest=sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35
amd64_manifest=sha256:ad7d8e8ef69e3dcc1ad08339b12c0c118bf98b9602b89f66aa5efc236e1df41a
seed_manifest_sha=a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2
strict_floor=71.29326283364946
strict_best=71.39843006187554

dockerc() {
  sudo -S -p '' docker "$@" < "$sudo_pass_file"
}

remote_amd64_manifest=$(
  dockerc manifest inspect --verbose vllm/vllm-openai-xpu:nightly |
    jq -r '.[] | select(.Descriptor.platform.os == "linux" and .Descriptor.platform.architecture == "amd64") | .Descriptor.digest'
)
[[ "$remote_amd64_manifest" == "$amd64_manifest" ]] || {
  echo "error: rolling nightly advanced to $remote_amd64_manifest; remap the overlay" >&2
  exit 3
}

[[ "$(sha256sum "$overlay/manifest.sha256" | awk '{print $1}')" == \
   "$seed_manifest_sha" ]] || {
  echo "error: tracked seed manifest changed" >&2
  exit 3
}
(
  cd "$seed"
  sha256sum -c ../manifest.sha256 >/dev/null
)

required_bytes=1073741824
[[ "$mode" == "fresh" ]] && required_bytes=2147483648
available_bytes=$(df -B1 --output=avail "$(dirname -- "$cache")" | tail -n 1)
(( available_bytes >= required_bytes )) || {
  echo "error: mode $mode requires at least $required_bytes bytes free on ext4" >&2
  exit 3
}

common_env=(
  SUDO_PASS_FILE="$sudo_pass_file"
  SOURCE_IMAGE_TAG=vllm/vllm-openai-xpu:nightly
  PULL_SOURCE_IMAGE=0
  EXPECTED_RESOLVED_IMAGE_DIGEST="$image_digest"
  EXPECTED_IMAGE_ID="$image_digest"
  VLLM_XPU_GRAPH=1
  REQUIRE_GRAPH_CAPTURE=1
  GPU_MEM_UTIL=0.60
  CANARY=1
  BENCH=1
  MAX_TOKENS=512
  RETURN_TOKEN_IDS=1
)

run_clean_env() {
  env -u PYTHONHASHSEED \
    -u VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE \
    -u VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING \
    -u TRITON_CACHE_AUTOTUNING -u VLLM_XPU_ENABLE_XPU_GRAPH \
    -u EXTRA_VLLM_ARGS -u PROMPT_IDS -u ONEAPI_DEVICE_SELECTOR \
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

outer_cache_manifest() {
  local destination=$1
  sudo -S -p '' bash -c '
    cd "$1" || exit 1
    find . -type f -print0 | sort -z | xargs -0 -r sha256sum
  ' bash "$cache" < "$sudo_pass_file" > "$destination"
}

if [[ "$mode" == "fresh" ]]; then
  run_clean_env "${common_env[@]}" \
    CACHE_POLICY=seeded-fresh \
    BEST_CONFIG_SEED_DIR="$seed" \
    EXPECTED_BEST_CONFIG_SEED_COUNT=152 \
    EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256="$seed_manifest_sha" \
    BEST_CONFIG_TARGET_AOT_NAMESPACE=38ae410d48b6f2f743b9745c8fe56b918c015ce7f60eeff9f979681a8f50d900 \
    EXPECTED_CACHE_OUTER_NAMESPACE=b9937c3e95 \
    EXPECTED_CACHE_CODE_HASH=a855541ceda97900a2a4d8a4ce14bd76e348a01bc2d9a29c0001cc8b7b8cf2fa \
    EXPECTED_CACHE_COMPILER_HASH=ddcad03736 \
    EXPECTED_CACHE_CONFIG_HASH=97d85f2a6f \
    EXPECTED_CACHE_ENV_SHA256=3ea9c4136b7c8c83187ccad333e60c84e931340e1b5cbd308725b0e89f1d5f1d \
    EXPECTED_COMPUTATION_GRAPH_SHA256S=57ea9a3bfd4fe1500c8d43d51b539a39c97f26613d620fb9a713c3fd13fb7bb2,bcf7af786a4f7dbcc0a574f21e2e175e36e82a0b1418752417dc528543593f41,7999515793c588efdc955ab12a9e2fafe5c4b67bbc7203e0dde19f53196144ef,72a292416c8cf7904e2faa9b24e09f8545f7fa8bd028cb0967a7ea6a99673e0a \
    NATURAL_EOS=0 QUALITY=0 \
    "$runner" 0 f16 32768 0,1,2,3 19520 "$fresh_out" "$suite" "$cache"

  outer_cache_manifest "$fresh_out/cache-manifest.outer-final.sha256"
  cmp -s "$fresh_out/cache-manifest.post.sha256" \
    "$fresh_out/cache-manifest.outer-final.sha256" || {
    echo "error: cache changed while the fresh container was removed" >&2
    exit 4
  }

  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$fresh_out/bench.json")
  if awk -v actual="$actual" 'BEGIN { exit !(actual >= 71.5488) }'; then
    printf 'pass actual=%s historical_floor=71.5488\n' "$actual" \
      > "$fresh_out/overlay-speed-gate.status"
  else
    printf 'fail actual=%s historical_floor=71.5488\n' "$actual" \
      > "$fresh_out/overlay-speed-gate.status"
    echo "error: diagnostic overlay speed gate failed at $actual tok/s" >&2
    exit 5
  fi
  exit 0
fi

grep -qx 'pass' "$fresh_out/final.status"
grep -q '^pass ' "$fresh_out/overlay-speed-gate.status"
[[ "$(sha256sum "$baseline" | awk '{print $1}')" == \
   8215fb791e11b3e4c09056b4979c4739d3d855f2086c4786d45f2053c0342488 ]] || {
  echo "error: TP4 quality baseline identity changed" >&2
  exit 3
}
cache_manifest_sha=$(sha256sum "$fresh_out/cache-manifest.outer-final.sha256" |
  awk '{print $1}')

if [[ "$mode" == "replay-a" ]]; then
  run_clean_env "${common_env[@]}" \
    CACHE_POLICY=replay EXPECTED_CACHE_MANIFEST_SHA256="$cache_manifest_sha" \
    NATURAL_EOS=1 QUALITY=1 QUALITY_REQUIRE_BASELINE=1 \
    QUALITY_BASELINE_JSON="$baseline" \
    "$runner" 0 f16 32768 0,1,2,3 19521 "$replay_a_out" "$suite" "$cache"

  outer_cache_manifest "$replay_a_out/cache-manifest.outer-final.sha256"
  cmp -s "$fresh_out/cache-manifest.outer-final.sha256" \
    "$replay_a_out/cache-manifest.outer-final.sha256" || {
    echo "error: replay A changed the cache after final container removal" >&2
    exit 4
  }

  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$replay_a_out/bench.json")
  if awk -v actual="$actual" -v floor="$strict_floor" \
      'BEGIN { exit !(actual >= floor) }'; then
    printf 'pass actual=%s historical_floor=%s\n' "$actual" "$strict_floor" \
      > "$replay_a_out/overlay-strict-a-gate.status"
  else
    printf 'fail actual=%s historical_floor=%s\n' "$actual" "$strict_floor" \
      > "$replay_a_out/overlay-strict-a-gate.status"
    echo "error: strict overlay replay A gate failed at $actual tok/s" >&2
    exit 5
  fi
  exit 0
fi

grep -qx 'pass' "$replay_a_out/final.status"
grep -q '^pass ' "$replay_a_out/overlay-strict-a-gate.status"
run_clean_env "${common_env[@]}" \
  CACHE_POLICY=replay EXPECTED_CACHE_MANIFEST_SHA256="$cache_manifest_sha" \
  NATURAL_EOS=1 QUALITY=0 \
  "$runner" 0 f16 32768 0,1,2,3 19522 "$replay_b_out" "$suite" "$cache"

outer_cache_manifest "$replay_b_out/cache-manifest.outer-final.sha256"
cmp -s "$fresh_out/cache-manifest.outer-final.sha256" \
  "$replay_b_out/cache-manifest.outer-final.sha256" || {
  echo "error: replay B changed the cache after final container removal" >&2
  exit 4
}

actual_a=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
  "$replay_a_out/bench.json")
actual_b=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
  "$replay_b_out/bench.json")
if awk -v a="$actual_a" -v b="$actual_b" -v floor="$strict_floor" \
    -v best="$strict_best" \
    'BEGIN { high = (a > b ? a : b); exit !(a >= floor && b >= floor && high >= best) }'; then
  printf 'pass actual_a=%s actual_b=%s floor=%s best=%s\n' \
    "$actual_a" "$actual_b" "$strict_floor" "$strict_best" \
    > "$replay_b_out/overlay-stability-gate.status"
else
  printf 'fail actual_a=%s actual_b=%s floor=%s best=%s\n' \
    "$actual_a" "$actual_b" "$strict_floor" "$strict_best" \
    > "$replay_b_out/overlay-stability-gate.status"
  echo "error: TP4 overlay stability gate failed at $actual_a / $actual_b tok/s" >&2
  exit 5
fi
