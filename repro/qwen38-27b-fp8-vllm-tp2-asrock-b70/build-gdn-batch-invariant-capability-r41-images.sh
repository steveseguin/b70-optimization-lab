#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../.." && pwd)
dockerfile=${script_dir}/Dockerfile.gdn-batch-invariant-capability
patch_file=${repo}/experiments/qwen38-27b-b70/patches/vllm-qwen38-gdn-serial-batch-invariant-capability-r37b-20260828.patch
patch_sha=73d6f9f51b5dff68ededf25fb1f4a3abaf5395435e65fff0743eb5c203156197

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${patch_sha}" ]] || fail 'capability patch identity changed'
[[ -z "$(git -C "${repo}" status --porcelain --untracked-files=no)" ]] || fail 'tracked repository files must be clean'

build_one() {
  local base=$1 expected_id=$2 output=$3 actual
  actual=$(docker image inspect "${base}" --format '{{.Id}}' 2>/dev/null) || fail "base image missing: ${base}"
  [[ "${actual}" == "${expected_id}" ]] || fail "base image identity mismatch: ${base}"
  docker image inspect "${output}" >/dev/null 2>&1 && fail "refusing to overwrite image: ${output}"
  docker build --pull=false \
    --build-arg "BASE_IMAGE=${base}" \
    --build-arg "EXPECTED_BASE_IMAGE_ID=${expected_id}" \
    --build-arg "GDN_CAPABILITY_PATCH_SHA256=${patch_sha}" \
    --file "${dockerfile}" --tag "${output}" "${repo}"
  [[ "$(docker image inspect "${output}" --format '{{ index .Config.Labels "neural.download.composite.base" }}')" == "${expected_id}" ]] || fail 'output base label mismatch'
  [[ "$(docker image inspect "${output}" --format '{{ index .Config.Labels "neural.download.vllm.gdn-capability.patch.sha256" }}')" == "${patch_sha}" ]] || fail 'output patch label mismatch'
}

build_one \
  neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-r15 \
  sha256:d19f802ba702a9cb94b155f807a4674a0100702aee838323372f740d7168e34e \
  neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-bi-r41
build_one \
  neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31 \
  sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b \
  neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-bi-r41

docker image inspect \
  neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-bi-r41 \
  neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-bi-r41
