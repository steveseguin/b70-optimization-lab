#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
base=neural-download/vllm-openai-xpu:qwen38-autoround-decoder-stage-sync-r1
expected_base=sha256:a1454ebe9adc227b0dc5eb867c2b9a58ca12cc2594a41c4f070118d6f04cc13c
vllm_head=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
image=neural-download/vllm-openai-xpu:qwen38-autoround-profile-only-decoder-sync-r1
patch_name=vllm-qwen38-profile-only-decoder-stage-sync-20260831.patch
patch_path="$repo/experiments/qwen38-27b-b70/patches/$patch_name"
dockerfile="$repo/experiments/qwen38-27b-b70/docker/Dockerfile.autoround-profile-only-decoder-sync-r1"
context=$(mktemp -d /tmp/qwen38-profile-only-decoder-sync.XXXXXX)
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
decoder_source = inspect.getsource(Qwen3NextDecoderLayer.forward)
profile_source = inspect.getsource(GPUModelRunner.profile_run)
assert "VLLM_XPU_QWEN38_PROFILE_SYNC_ACTIVE" in decoder_source
assert "VLLM_XPU_QWEN38_PROFILE_SYNC_ACTIVE" in profile_source
assert profile_source.count("VLLM_XPU_QWEN38_PROFILE_SYNC_ACTIVE") == 2
print("profile_only_decoder_stage_sync_runtime=pass")
'
