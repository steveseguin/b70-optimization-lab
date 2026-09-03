#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:901ae9e0ade0109e94dd162d0cf2c398440325b1791f3191376fa0013dc29878}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-triton-rmsnorm-r153a}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-triton-rmsnorm-r153a-20260902.patch
validator=${repo_root}/tools/validate-xpu-triton-rmsnorm-r153a.py
expected_patch_sha256=c86f5f78e230bd7b4d28d0e925693af11924e8d2a513004f2d8b66a0b8af680d
expected_xpu_sha256=37c65a77cd398e4d560f797c74c236336910683dfed3a2dc8259878d86e456a9
xpu_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/layernorm.py
dockerfile=${script_dir}/Dockerfile.triton-rmsnorm-r153a

for command_name in docker patch python3 sha256sum; do
  command -v "${command_name}" >/dev/null || { printf 'ERROR: missing %s\n' "${command_name}" >&2; exit 2; }
done
for required in "${dockerfile}" "${patch_file}" "${validator}"; do
  [[ -f "${required}" ]] || { printf 'ERROR: missing build input: %s\n' "${required}" >&2; exit 2; }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || { printf 'ERROR: R153a patch mismatch\n' >&2; exit 2; }
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
[[ "${observed}" == "${expected_xpu_sha256}" ]] || { printf 'ERROR: installed R153a layernorm.py mismatch: %s\n' "${observed}" >&2; exit 2; }
docker run --rm --entrypoint /opt/venv/bin/python \
  --volume "${validator}:/tmp/validate-xpu-triton-rmsnorm-r153a.py:ro" \
  "${image}" /tmp/validate-xpu-triton-rmsnorm-r153a.py "${xpu_file}"
printf '%s\n' "image=${image}" "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" "xpu_source_sha256=${observed}"
