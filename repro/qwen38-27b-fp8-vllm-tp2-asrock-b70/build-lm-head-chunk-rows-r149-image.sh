#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:901ae9e0ade0109e94dd162d0cf2c398440325b1791f3191376fa0013dc29878}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-lm-head-chunk-rows-r149}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-lm-head-chunk-rows-r149-20260902.patch
validator=${repo_root}/tools/validate-xpu-lm-head-chunk-rows-r149.py
expected_patch_sha256=ed43af629b1bc1ea932462cb3399ac44435f3db2bdd5c2a1dd4f9dff6b3bbee8
expected_xpu_sha256=0d8f0ffc91a7f7effa05c8607953b0a9a7b50b710aaf8aca05676f385c978d4d
xpu_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/logits_processor.py
dockerfile=${script_dir}/Dockerfile.lm-head-chunk-rows-r149

for command_name in docker patch python3 sha256sum; do
  command -v "${command_name}" >/dev/null || { printf 'ERROR: missing %s\n' "${command_name}" >&2; exit 2; }
done
for required in "${dockerfile}" "${patch_file}" "${validator}"; do
  [[ -f "${required}" ]] || { printf 'ERROR: missing build input: %s\n' "${required}" >&2; exit 2; }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || { printf 'ERROR: R149 patch mismatch\n' >&2; exit 2; }
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || { printf 'ERROR: R139 base image mismatch\n' >&2; exit 2; }
[[ ! -e "${build_root}" ]] || { printf 'ERROR: BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2; exit 2; }

mkdir -p "${build_root}"
install -m 0644 "${patch_file}" "${build_root}/$(basename -- "${patch_file}")"
install -m 0644 "${validator}" "${build_root}/$(basename -- "${validator}")"

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "LM_HEAD_CHUNK_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" "${xpu_file}" | awk '{print $1}')
[[ "${observed}" == "${expected_xpu_sha256}" ]] || { printf 'ERROR: installed R149 logits_processor.py mismatch: %s\n' "${observed}" >&2; exit 2; }
docker run --rm --entrypoint /opt/venv/bin/python \
  --volume "${validator}:/tmp/validate-xpu-lm-head-chunk-rows-r149.py:ro" \
  "${image}" /tmp/validate-xpu-lm-head-chunk-rows-r149.py "${xpu_file}"
printf '%s\n' "image=${image}" "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" "xpu_source_sha256=${observed}"
