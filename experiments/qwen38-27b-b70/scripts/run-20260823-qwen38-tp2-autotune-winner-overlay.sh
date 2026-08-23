#!/usr/bin/env bash
set -euo pipefail

mode=${1:?usage: $0 fresh|replay}
[[ "$mode" == "fresh" || "$mode" == "replay" ]] || {
  echo "error: mode must be fresh or replay" >&2
  exit 2
}

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
runner="$repo/experiments/qwen38-27b-b70/scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh"
suite="$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json"
overlay="$repo/experiments/qwen38-27b-b70/autotune-winner-overlays/tp2-e9d1398-best-config"
seed="$overlay/source"
result_root=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/rolling-nightly-a3561ef8e
fresh_out="$result_root/tp2-graph-autotune-winner-seeded-fresh"
replay_out="$result_root/tp2-graph-autotune-winner-strict-quality-replay"
cache=/mnt/fast-ai/runtime/qwen38-rolling-a3561ef8e/tp2-autotune-winner-cache
baseline=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp2-mtp0-f16-graph-natural-eos-replay-b-baseline-quality/quality.json
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}

image_digest=sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35
amd64_manifest=sha256:ad7d8e8ef69e3dcc1ad08339b12c0c118bf98b9602b89f66aa5efc236e1df41a
seed_manifest_sha=65c574c24d24804d250e5179e9a202ec9e77e8c5740cea121b7660d8ee854757

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

available_bytes=$(df -B1 --output=avail "$(dirname -- "$cache")" | tail -n 1)
(( available_bytes >= 1073741824 )) || {
  echo "error: seeded compile requires at least 1 GiB free on ext4" >&2
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
  GPU_MEM_UTIL=0.90
  CANARY=1
  BENCH=1
  MAX_TOKENS=512
  RETURN_TOKEN_IDS=1
)

if [[ "$mode" == "fresh" ]]; then
  env -u PYTHONHASHSEED \
    -u VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE \
    -u VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING \
    -u TRITON_CACHE_AUTOTUNING -u VLLM_XPU_ENABLE_XPU_GRAPH \
    -u EXTRA_VLLM_ARGS -u PROMPT_IDS -u ONEAPI_DEVICE_SELECTOR \
    -u QUALITY_BASELINE_JSON -u QUALITY_REQUIRE_BASELINE \
    "${common_env[@]}" \
    CACHE_POLICY=seeded-fresh \
    BEST_CONFIG_SEED_DIR="$seed" \
    EXPECTED_BEST_CONFIG_SEED_COUNT=78 \
    EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256="$seed_manifest_sha" \
    BEST_CONFIG_TARGET_AOT_NAMESPACE=6c4068168dd6c78f99626fb8a564532e4c66736e11b3fe5bf3d94b37e6e221d2 \
    EXPECTED_CACHE_OUTER_NAMESPACE=960928a3a2 \
    EXPECTED_CACHE_CODE_HASH=a855541ceda97900a2a4d8a4ce14bd76e348a01bc2d9a29c0001cc8b7b8cf2fa \
    EXPECTED_CACHE_COMPILER_HASH=ddcad03736 \
    EXPECTED_CACHE_CONFIG_HASH=1a5f4b8e61 \
    EXPECTED_CACHE_ENV_SHA256=3ea9c4136b7c8c83187ccad333e60c84e931340e1b5cbd308725b0e89f1d5f1d \
    EXPECTED_COMPUTATION_GRAPH_SHA256S=5af6d45fbb1a676f8e8606800d2153daed6d43d826b96212d8e104a516ee6b82,2410abd8643255686155cecb16881b23d9b20075b745cb5f62e34bf77a2dcb6f \
    NATURAL_EOS=0 QUALITY=0 \
    "$runner" 0 f16 32768 2,3 19518 "$fresh_out" "$suite" "$cache"

  actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
    "$fresh_out/bench.json")
  if awk -v actual="$actual" 'BEGIN { exit !(actual >= 48.8301) }'; then
    printf 'pass actual=%s historical_floor=48.8301\n' "$actual" \
      > "$fresh_out/overlay-speed-gate.status"
  else
    printf 'fail actual=%s historical_floor=48.8301\n' "$actual" \
      > "$fresh_out/overlay-speed-gate.status"
    echo "error: diagnostic overlay speed gate failed at $actual tok/s" >&2
    exit 5
  fi
  exit 0
fi

grep -qx 'pass' "$fresh_out/final.status"
grep -q '^pass ' "$fresh_out/overlay-speed-gate.status"
[[ "$(sha256sum "$baseline" | awk '{print $1}')" == \
   0ba49be19bbb081023259ce290f87990d3e26038e461d136862631442a63bc48 ]] || {
  echo "error: TP2 quality baseline identity changed" >&2
  exit 3
}
cache_manifest_sha=$(sha256sum "$fresh_out/cache-manifest.post.sha256" |
  awk '{print $1}')

env -u PYTHONHASHSEED \
  -u VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE \
  -u VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING \
  -u TRITON_CACHE_AUTOTUNING -u VLLM_XPU_ENABLE_XPU_GRAPH \
  -u EXTRA_VLLM_ARGS -u PROMPT_IDS -u ONEAPI_DEVICE_SELECTOR \
  "${common_env[@]}" \
  CACHE_POLICY=replay EXPECTED_CACHE_MANIFEST_SHA256="$cache_manifest_sha" \
  NATURAL_EOS=1 QUALITY=1 QUALITY_REQUIRE_BASELINE=1 \
  QUALITY_BASELINE_JSON="$baseline" \
  "$runner" 0 f16 32768 2,3 19519 "$replay_out" "$suite" "$cache"

actual=$(jq -r '.summary.tok_s_1_100_intervals_after_ttft.median' \
  "$replay_out/bench.json")
if awk -v actual="$actual" 'BEGIN { exit !(actual >= 49.01965141150585) }'; then
  printf 'pass actual=%s historical_floor=49.01965141150585\n' "$actual" \
    > "$replay_out/overlay-strict-speed-gate.status"
else
  printf 'fail actual=%s historical_floor=49.01965141150585\n' "$actual" \
    > "$replay_out/overlay-strict-speed-gate.status"
  echo "error: strict overlay speed gate failed at $actual tok/s" >&2
  exit 5
fi
