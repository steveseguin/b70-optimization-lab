#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-w8a16-decode-pad-rows-r118}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:95742ce8493671fb28b0b53db77a2f0c240e8d82355f20b756ab2479d037b8d0}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-w8a16-pad-n-set-prealloc-r118b}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-w8a16-pad-n-set-prealloc-r118b-20260902.patch
validator=${repo_root}/tools/validate-xpu-w8a16-pad-n-set-prealloc-r118b.py
expected_patch_sha256=111bc43ff7de7476986b0a078bd95614315c797e254ea4c80e6f878de4e16c67
expected_xpu_sha256=a4ba3f34e4f92892a1b85eec3504704811436f20fbac299594540aac54f3be7a
xpu_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/kernels/linear/scaled_mm/xpu.py
dockerfile=${script_dir}/Dockerfile.w8a16-pad-n-set-prealloc-r118b

for command_name in docker patch python3 sha256sum; do
  command -v "${command_name}" >/dev/null || { printf 'ERROR: missing %s\n' "${command_name}" >&2; exit 2; }
done
for required in "${dockerfile}" "${patch_file}" "${validator}"; do
  [[ -f "${required}" ]] || { printf 'ERROR: missing build input: %s\n' "${required}" >&2; exit 2; }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || { printf 'ERROR: R118b patch mismatch\n' >&2; exit 2; }
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || { printf 'ERROR: R118 base image mismatch\n' >&2; exit 2; }
[[ ! -e "${build_root}" ]] || { printf 'ERROR: BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2; exit 2; }

mkdir -p "${build_root}"
install -m 0644 "${patch_file}" "${build_root}/$(basename -- "${patch_file}")"
install -m 0644 "${validator}" "${build_root}/$(basename -- "${validator}")"

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "W8A16_PAD_N_SET_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" "${xpu_file}" | awk '{print $1}')
[[ "${observed}" == "${expected_xpu_sha256}" ]] || { printf 'ERROR: installed R118b xpu.py mismatch: %s\n' "${observed}" >&2; exit 2; }
docker run --rm --entrypoint /opt/venv/bin/python \
  --volume "${validator}:/tmp/validate-xpu-w8a16-pad-n-set-prealloc-r118b.py:ro" \
  "${image}" /tmp/validate-xpu-w8a16-pad-n-set-prealloc-r118b.py "${xpu_file}"
printf '%s\n' "image=${image}" "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" "xpu_source_sha256=${observed}"
