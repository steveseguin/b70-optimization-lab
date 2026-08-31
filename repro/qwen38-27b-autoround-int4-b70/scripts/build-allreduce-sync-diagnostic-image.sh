#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repro_dir=$(cd -- "${script_dir}/.." && pwd)
repo=$(cd -- "${repro_dir}/../.." && pwd)
base=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-autoround-allreduce-sync-diagnostic-r4}
source_path=/opt/venv/lib/python3.12/site-packages/vllm/distributed/device_communicators/xpu_communicator.py
expected_source_sha=5ab2ea5d9e049e6b53e2d56d1e3419ce01d1988e8be5295bab1f912a7fdbf74d
patch_file=${repo}/experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-allreduce-device-sync-diagnostic-20260830.patch

[[ "$(docker image inspect "$base" --format '{{.Id}}')" == "$expected_base_id" ]] || {
  printf 'base image identity mismatch\n' >&2
  exit 1
}

build_root=$(mktemp -d /tmp/qwen38-allreduce-sync-build.XXXXXX)
container=
cleanup() {
  [[ -z "$container" ]] || docker rm -f "$container" >/dev/null 2>&1 || true
  find "$build_root" -xdev -depth -delete
}
trap cleanup EXIT

mkdir -p "$build_root/vllm/distributed/device_communicators"
container=$(docker create "$base")
docker cp "${container}:${source_path}" \
  "$build_root/vllm/distributed/device_communicators/xpu_communicator.py"
docker rm "$container" >/dev/null
container=
printf '%s  %s\n' "$expected_source_sha" \
  "$build_root/vllm/distributed/device_communicators/xpu_communicator.py" \
  | sha256sum -c -
patch -d "$build_root" -p1 <"$patch_file"
cp "$repro_dir/Dockerfile.allreduce-sync-diagnostic" "$build_root/Dockerfile"
new_sha=$(sha256sum \
  "$build_root/vllm/distributed/device_communicators/xpu_communicator.py" \
  | awk '{print $1}')
docker build \
  --build-arg "BASE_IMAGE=$base" \
  --label "neural.download.base.image.id=$expected_base_id" \
  --label "neural.download.treatment=allreduce-work-wait-plus-device-sync-diagnostic" \
  --label "neural.download.xpu-communicator.sha256=$new_sha" \
  --tag "$image" "$build_root"

actual_sha=$(docker run --rm --entrypoint sha256sum "$image" "$source_path" | awk '{print $1}')
[[ "$actual_sha" == "$new_sha" ]] || { printf 'overlay identity mismatch\n' >&2; exit 1; }
printf 'image=%s\nimage_id=%s\nxpu_communicator_sha256=%s\n' \
  "$image" "$(docker image inspect "$image" --format '{{.Id}}')" "$new_sha"
