#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
dockerfile="$repo/experiments/qwen38-27b-b70/docker/Dockerfile.fp8-w8a16-dynamic-sd-latch-r2"
patch="$repo/experiments/qwen38-27b-b70/patches/vllm-qwen38-dynamic-sd-busy-period-latch-reset-after-free-20260827.patch"
image="${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-sd-latch-r2}"
expected_patch=fe42ed628041032f51cf456ffcc03136f57be9415f34f32354965a655a2b13bf

[[ "$(sha256sum "$patch" | awk '{print $1}')" == "$expected_patch" ]]
docker build \
  --file "$dockerfile" \
  --build-arg "PATCH_SHA256=$expected_patch" \
  --tag "$image" \
  "$repo"
docker image inspect "$image" --format '{{.Id}}'
