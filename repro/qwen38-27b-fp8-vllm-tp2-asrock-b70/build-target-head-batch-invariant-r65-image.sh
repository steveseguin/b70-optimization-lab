#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-target-head-batch-invariant-r65}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-draft-only-int4-r62}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:cac17acf96ebbf65bfbe98e45dcea8eb5626c2b027dcac0228bc3bcba0063374}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-target-head-batch-invariant-r65-20260901.patch
dockerfile=${script_dir}/Dockerfile.target-head-batch-invariant-r65
expected_base_sha256=a67215084b55800174b37166e7e74593e62e4b2d7460da59ad2eb4a23c8c8ba7
expected_patch_sha256=e87e8c0a2e9b6b6907ff079a6c4f807bbf3b3cf218f0a01064eb3a264bff361f
source_rel=vllm/model_executor/layers/vocab_parallel_embedding.py

for command_name in docker patch sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${patch_file}" "${dockerfile}"; do
  [[ -f "${required}" ]] || {
    printf 'missing build input: %s\n' "${required}" >&2
    exit 1
  }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || {
  printf 'target-head batch-invariant patch identity mismatch\n' >&2
  exit 1
}
[[ ! -e "${build_root}" ]] || {
  printf 'BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 1
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'base image identity mismatch\n' >&2
  exit 1
}

mkdir -p "${build_root}/$(dirname -- "${source_rel}")"
container=$(docker create "${base_image}")
cleanup() { docker rm -f "${container}" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM
docker cp \
  "${container}:/opt/venv/lib/python3.12/site-packages/${source_rel}" \
  "${build_root}/${source_rel}"
cleanup
trap - EXIT INT TERM
[[ "$(sha256sum "${build_root}/${source_rel}" | awk '{print $1}')" == "${expected_base_sha256}" ]] || {
  printf 'base source identity mismatch: %s\n' "${source_rel}" >&2
  exit 1
}

patch --directory="${build_root}" --strip=1 --forward --batch <"${patch_file}"
vocab_sha256=$(sha256sum "${build_root}/${source_rel}" | awk '{print $1}')

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "VOCAB_SOURCE_SHA256=${vocab_sha256}" \
  --build-arg "TARGET_HEAD_BATCH_INVARIANT_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" \
  "/opt/venv/lib/python3.12/site-packages/${source_rel}" | awk '{print $1}')
[[ "${observed}" == "${vocab_sha256}" ]] || {
  printf 'built vocabulary source hash mismatch\n' >&2
  exit 1
}
printf 'image=%s\nimage_id=%s\nvocab_sha256=%s\npatch_sha256=%s\n' \
  "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')" \
  "${vocab_sha256}" "${expected_patch_sha256}"
