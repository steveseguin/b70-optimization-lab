#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
base=neural-download/vllm-openai-xpu:qwen38-autoround-dummy-sampler-stage-sync-r1
expected_base=sha256:66bcfff69c6bf49500ce564132b303b26e26793c2c7c1b75a03c47681cab7261
vllm_head=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
image=neural-download/vllm-openai-xpu:qwen38-autoround-decoder-stage-sync-r1
patch_name=vllm-qwen38-decoder-stage-sync-20260831.patch
patch_path="$repo/experiments/qwen38-27b-b70/patches/$patch_name"
dockerfile="$repo/experiments/qwen38-27b-b70/docker/Dockerfile.autoround-decoder-stage-sync-r1"
context=$(mktemp -d /tmp/qwen38-decoder-stage-sync.XXXXXX)
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
from vllm.model_executor.models.qwen3_next import Qwen3NextDecoderLayer
from vllm.v1.worker.gpu_model_runner import GPUModelRunner
decoder_path = inspect.getsourcefile(Qwen3NextDecoderLayer)
decoder_source = inspect.getsource(Qwen3NextDecoderLayer.forward)
sampler_path = inspect.getsourcefile(GPUModelRunner)
sampler_source = inspect.getsource(GPUModelRunner._dummy_sampler_run)
assert decoder_path == "/workspace/vllm/vllm/model_executor/models/qwen3_next.py"
assert sampler_path == "/workspace/vllm/vllm/v1/worker/gpu_model_runner.py"
assert decoder_source.count("QWEN38_DECODER_STAGE_SYNC") == 3
assert decoder_source.count("stage_sync(") >= 8
assert sampler_source.count("QWEN38_DUMMY_SAMPLER_STAGE_SYNC") == 3
print("active_runtime_decoder_and_sampler_stage_sync=pass")
'
