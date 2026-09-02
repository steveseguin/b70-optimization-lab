#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-r99-all-phases-r117}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:52fe73b06d0cbef8c2a007f48f06ff77831b2589fec5d04590e10f079266eedf}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-w8a16-decode-pad-rows-r118}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-w8a16-decode-pad-rows-r118-20260902.patch
validator=${repo_root}/tools/validate-xpu-w8a16-decode-pad-rows-r118.py
expected_patch_sha256=9853f37feba7806ca62ab210efd47cd0dc4d6ef12dcde5d0e1e8d915f3be2a67
expected_xpu_sha256=e9addee16baae25bfc603a26070cfd9558be8f3bba63fee16642c439288ad752
xpu_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/kernels/linear/scaled_mm/xpu.py
dockerfile=${script_dir}/Dockerfile.w8a16-decode-pad-rows-r118

for command_name in docker patch python3 sha256sum; do
  command -v "${command_name}" >/dev/null || { printf 'ERROR: missing %s\n' "${command_name}" >&2; exit 2; }
done
for required in "${dockerfile}" "${patch_file}" "${validator}"; do
  [[ -f "${required}" ]] || { printf 'ERROR: missing build input: %s\n' "${required}" >&2; exit 2; }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || { printf 'ERROR: R118 patch mismatch\n' >&2; exit 2; }
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || { printf 'ERROR: R117 base image mismatch\n' >&2; exit 2; }
[[ ! -e "${build_root}" ]] || { printf 'ERROR: BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2; exit 2; }

mkdir -p "${build_root}"
install -m 0644 "${patch_file}" "${build_root}/$(basename -- "${patch_file}")"
install -m 0644 "${validator}" "${build_root}/$(basename -- "${validator}")"

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "W8A16_DECODE_PAD_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" "${xpu_file}" | awk '{print $1}')
[[ "${observed}" == "${expected_xpu_sha256}" ]] || { printf 'ERROR: installed R118 xpu.py mismatch: %s\n' "${observed}" >&2; exit 2; }
docker run --rm --entrypoint /opt/venv/bin/python \
  --volume "${validator}:/tmp/validate-xpu-w8a16-decode-pad-rows-r118.py:ro" \
  "${image}" /tmp/validate-xpu-w8a16-decode-pad-rows-r118.py "${xpu_file}"
printf '%s\n' "image=${image}" "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" "xpu_source_sha256=${observed}"
