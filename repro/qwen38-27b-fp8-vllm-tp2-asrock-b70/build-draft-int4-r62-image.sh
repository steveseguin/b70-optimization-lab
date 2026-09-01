#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-draft-only-int4-r62}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50-reprocheck-r55c}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:41aec5da9b124497a9b5dbc6b38f17175bf923d930d5702b9913589f107802d4}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-draft-only-int4-lm-head-r62-20260901.patch
dockerfile=${script_dir}/Dockerfile.draft-int4-r62
expected_patch_sha256=594ee1a38fef377bba34db98f2fd7f51641ea9697b4bb622c9a54634b0bd87ab
source_rels=(
  vllm/model_executor/layers/vocab_parallel_embedding.py
  vllm/v1/spec_decode/llm_base_proposer.py
)
expected_base_hashes=(
  b3e8a07296607153424b4b7ca5f75f00dcec1bce0f49e54b5eff6262fdf80201
  5f8ec3139413bac8a5694c2c8a535e29b665e5496f0abc70eea5628bf4b68164
)

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
  printf 'draft INT4 patch identity mismatch\n' >&2
  exit 1
}
[[ ! -e "${build_root}" ]] || {
  printf 'BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 1
}

"${script_dir}/verify-image-contract.sh" mtp1-serial-fa-split-gdn "${base_image}"
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'base image identity mismatch\n' >&2
  exit 1
}

container=$(docker create "${base_image}")
cleanup() { docker rm -f "${container}" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM
for index in "${!source_rels[@]}"; do
  source_rel=${source_rels[index]}
  mkdir -p "${build_root}/$(dirname -- "${source_rel}")"
  docker cp \
    "${container}:/opt/venv/lib/python3.12/site-packages/${source_rel}" \
    "${build_root}/${source_rel}"
  [[ "$(sha256sum "${build_root}/${source_rel}" | awk '{print $1}')" == "${expected_base_hashes[index]}" ]] || {
    printf 'base source identity mismatch: %s\n' "${source_rel}" >&2
    exit 1
  }
done
cleanup
trap - EXIT INT TERM

patch --directory="${build_root}" --strip=1 --forward --batch <"${patch_file}"
vocab_sha256=$(sha256sum "${build_root}/${source_rels[0]}" | awk '{print $1}')
proposer_sha256=$(sha256sum "${build_root}/${source_rels[1]}" | awk '{print $1}')

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "VOCAB_SOURCE_SHA256=${vocab_sha256}" \
  --build-arg "PROPOSER_SOURCE_SHA256=${proposer_sha256}" \
  --build-arg "DRAFT_INT4_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

mapfile -t observed < <(
  docker run --rm --entrypoint sha256sum "${image}" \
    "/opt/venv/lib/python3.12/site-packages/${source_rels[0]}" \
    "/opt/venv/lib/python3.12/site-packages/${source_rels[1]}" |
    awk '{print $1}'
)
[[ "${observed[0]}" == "${vocab_sha256}" ]] || {
  printf 'built vocabulary source hash mismatch\n' >&2
  exit 1
}
[[ "${observed[1]}" == "${proposer_sha256}" ]] || {
  printf 'built proposer source hash mismatch\n' >&2
  exit 1
}
printf 'image=%s\nimage_id=%s\nvocab_sha256=%s\nproposer_sha256=%s\npatch_sha256=%s\n' \
  "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')" \
  "${vocab_sha256}" "${proposer_sha256}" "${expected_patch_sha256}"
