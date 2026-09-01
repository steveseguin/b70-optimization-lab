#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-linear-r48}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-mtp1-packed-linear-serial-r48-20260901.patch
dockerfile=${script_dir}/Dockerfile.mtp1-serial-linear
fp8_rel=vllm/model_executor/layers/quantization/fp8.py

for command_name in docker patch sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${patch_file}" "${dockerfile}"; do
  [[ -f "${required}" ]] || { printf 'missing build input: %s\n' "${required}" >&2; exit 1; }
done
[[ ! -e "${build_root}" ]] || {
  printf 'BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 1
}

"${script_dir}/verify-image-contract.sh" mtp1 "${base_image}"
mkdir -p "${build_root}/$(dirname -- "${fp8_rel}")"
container=$(docker create "${base_image}")
cleanup() { docker rm -f "${container}" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM
docker cp \
  "${container}:/opt/venv/lib/python3.12/site-packages/${fp8_rel}" \
  "${build_root}/${fp8_rel}"
cleanup
trap - EXIT INT TERM

patch --directory="${build_root}" --strip=1 --forward --batch <"${patch_file}"
fp8_sha256=$(sha256sum "${build_root}/${fp8_rel}" | awk '{print $1}')
patch_sha256=$(sha256sum "${patch_file}" | awk '{print $1}')

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "FP8_PY_SHA256=${fp8_sha256}" \
  --build-arg "FP8_PATCH_SHA256=${patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

printf 'image=%s\nimage_id=%s\nfp8_sha256=%s\npatch_sha256=%s\n' \
  "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')" \
  "${fp8_sha256}" "${patch_sha256}"
