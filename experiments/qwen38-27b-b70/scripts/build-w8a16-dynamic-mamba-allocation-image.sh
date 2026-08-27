#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
dockerfile="$repo/experiments/qwen38-27b-b70/docker/Dockerfile.fp8-w8a16-dynamic-mamba-allocation-r1"
patch="$repo/experiments/qwen38-27b-b70/patches/vllm-qwen38-dynamic-mtp-mamba-active-allocation-20260826.patch"
image="${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1}"
expected_patch=3334c37f33677e4a499aa5959f79fb78d2fa47a39a350ab4bd1a120169512190

[[ "$(sha256sum "$patch" | awk '{print $1}')" == "$expected_patch" ]]
docker build \
  --file "$dockerfile" \
  --build-arg "PATCH_SHA256=$expected_patch" \
  --tag "$image" \
  "$repo"
docker image inspect "$image" --format '{{.Id}}'
