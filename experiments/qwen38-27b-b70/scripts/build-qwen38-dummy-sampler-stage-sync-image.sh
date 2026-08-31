#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
base=neural-download/vllm-openai-xpu:qwen38-autoround-gdn-int4-prefill-pad512-r1
expected_base=sha256:03da963d9d9b3b2cfc5cb7d9f1bc0aeb9ebd7e1b9495e3cad4e5b9e5dd4fc493
vllm_head=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
image=neural-download/vllm-openai-xpu:qwen38-autoround-dummy-sampler-stage-sync-r1
patch_name=vllm-qwen38-dummy-sampler-stage-sync-20260831.patch
patch_path="$repo/experiments/qwen38-27b-b70/patches/$patch_name"
dockerfile="$repo/experiments/qwen38-27b-b70/docker/Dockerfile.autoround-dummy-sampler-stage-sync-r1"
context=$(mktemp -d /tmp/qwen38-dummy-sampler-stage-sync.XXXXXX)
cleanup() { rm -rf -- "$context"; }
trap cleanup EXIT

actual_base=$(docker image inspect "$base" --format '{{.Id}}')
[[ "$actual_base" == "$expected_base" ]] || {
  printf 'base image mismatch: %s\n' "$actual_base" >&2
  exit 1
}
patch_sha=$(sha256sum "$patch_path" | awk '{print $1}')
install -m 0644 "$patch_path" "$context/$patch_name"

docker build --pull=false \
  --build-arg "BASE_IMAGE=$base" \
  --build-arg "BASE_IMAGE_ID=$expected_base" \
  --build-arg "PATCH_SHA256=$patch_sha" \
  --build-arg "VLLM_HEAD=$vllm_head" \
  --file "$dockerfile" --tag "$image" "$context"

docker image inspect "$image" --format \
  'id={{.Id}} base={{index .Config.Labels "neural.download.base.image.id"}} head={{index .Config.Labels "neural.download.vllm.head"}} patch={{index .Config.Labels "neural.download.vllm.patch.sha256"}}'
docker run --rm --entrypoint /opt/venv/bin/python "$image" -c '
import inspect
from vllm.v1.worker.gpu_model_runner import GPUModelRunner
source_path = inspect.getsourcefile(GPUModelRunner)
source = inspect.getsource(GPUModelRunner._dummy_sampler_run)
assert source_path == "/workspace/vllm/vllm/v1/worker/gpu_model_runner.py"
assert source.count("QWEN38_DUMMY_SAMPLER_STAGE_SYNC") == 3
assert source.count("stage_sync(") >= 10
print("active_runtime_stage_sync=pass")
'
