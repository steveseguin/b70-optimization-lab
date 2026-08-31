#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
base=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
expected_base=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136
vllm_head=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
image=neural-download/vllm-openai-xpu:qwen38-autoround-gdn-int4-prefill-pad512-r2
patch_name=vllm-qwen38-gdn-int4-prefill-pad512-determinism-20260831.patch
patch_path="$repo/experiments/qwen38-27b-b70/patches/$patch_name"
dockerfile="$repo/experiments/qwen38-27b-b70/docker/Dockerfile.autoround-gdn-int4-prefill-pad512-r1"
context=$(mktemp -d /tmp/qwen38-gdn-prefill-build.XXXXXX)
cleanup() { rm -rf -- "$context"; }
trap cleanup EXIT

actual_base=$(docker image inspect "$base" --format '{{.Id}}')
[[ "$actual_base" == "$expected_base" ]] || {
    printf 'base image mismatch: %s\n' "$actual_base" >&2
    exit 1
}
patch_sha=$(sha256sum "$patch_path" | awk '{print $1}')
install -m 0644 "$patch_path" "$context/$patch_name"

docker build --pull=false \
    --build-arg "BASE_IMAGE=$base" \
    --build-arg "BASE_IMAGE_ID=$expected_base" \
    --build-arg "PATCH_SHA256=$patch_sha" \
    --build-arg "VLLM_HEAD=$vllm_head" \
    --file "$dockerfile" --tag "$image" "$context"

docker image inspect "$image" --format \
    'id={{.Id}} base={{index .Config.Labels "neural.download.base.image.id"}} head={{index .Config.Labels "neural.download.vllm.head"}} patch={{index .Config.Labels "neural.download.vllm.patch.sha256"}}'
