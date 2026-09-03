#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-draft-int4-apply-rows-r160}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:3d425ec4355f5b514fbbb03cf6372677a393fd94e29a5d384617334955b41d45}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-triton-rmsnorm-r161}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-triton-rmsnorm-r153a2-20260902.patch
validator=${repo_root}/tools/validate-xpu-triton-rmsnorm-r153a2.py
expected_patch_sha256=19a02d0a29946ea9bfe579f46fefbc0e1009343e095b84d762ac2e5995cde720
expected_xpu_sha256=aaa48e514a42b3647b6a487baec69b46fea8a1a9e76a34f0de91dc6f88fe2530
xpu_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/layernorm.py
dockerfile=${script_dir}/Dockerfile.triton-rmsnorm-r161

for command_name in docker patch python3 sha256sum; do
  command -v "${command_name}" >/dev/null || { printf 'ERROR: missing %s\n' "${command_name}" >&2; exit 2; }
done
for required in "${dockerfile}" "${patch_file}" "${validator}"; do
  [[ -f "${required}" ]] || { printf 'ERROR: missing build input: %s\n' "${required}" >&2; exit 2; }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || { printf 'ERROR: R161 patch mismatch\n' >&2; exit 2; }
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || { printf 'ERROR: R139 base image mismatch\n' >&2; exit 2; }
[[ ! -e "${build_root}" ]] || { printf 'ERROR: BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2; exit 2; }

mkdir -p "${build_root}"
install -m 0644 "${patch_file}" "${build_root}/$(basename -- "${patch_file}")"
install -m 0644 "${validator}" "${build_root}/$(basename -- "${validator}")"

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "TRITON_RMSNORM_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" "${xpu_file}" | awk '{print $1}')
[[ "${observed}" == "${expected_xpu_sha256}" ]] || { printf 'ERROR: installed R161 layernorm.py mismatch: %s\n' "${observed}" >&2; exit 2; }
docker run --rm --entrypoint /opt/venv/bin/python \
  --volume "${validator}:/tmp/validate-xpu-triton-rmsnorm-r153a2.py:ro" \
  "${image}" /tmp/validate-xpu-triton-rmsnorm-r153a2.py "${xpu_file}"
printf '%s\n' "image=${image}" "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" "xpu_source_sha256=${observed}"
