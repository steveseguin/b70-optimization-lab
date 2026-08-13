#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)

source "${repo_root}/community/mndodd-qwen36-27b-llamacpp-sycl/runtime-common.sh"
source "${script_dir}/config.env"

server="${QWEN36_BUILD_DIR}/bin/llama-server"
if [[ ! -x "${server}" ]]; then
    printf 'Missing executable: %s\n' "${server}" >&2
    exit 1
fi
if [[ ! -f "${QWEN36_MODEL}" ]]; then
    printf 'Missing model: %s\n' "${QWEN36_MODEL}" >&2
    exit 1
fi

expected_model_sha=73f8260284708ed78ae266df672288b6ad1f2c73ec7ffeb7514b5cecdba646c9
actual_model_sha=$(sha256sum "${QWEN36_MODEL}" | awk '{print $1}')
if [[ "${actual_model_sha}" != "${expected_model_sha}" ]]; then
    printf 'Model SHA-256 mismatch: expected %s, got %s\n' \
        "${expected_model_sha}" "${actual_model_sha}" >&2
    exit 1
fi

exec systemd-run --user --scope --quiet \
    --property=MemoryHigh=8G \
    --property=MemoryMax=10G \
    --property=MemorySwapMax=8G \
    "${server}" \
    --model "${QWEN36_MODEL}" \
    --device SYCL0,SYCL1 \
    --gpu-layers 99 \
    --split-mode tensor \
    --tensor-split 1,1 \
    --flash-attn on \
    --batch-size 1024 \
    --ubatch-size 256 \
    --cache-type-k f16 \
    --cache-type-v f16 \
    --cache-ram 0 \
    --ctx-checkpoints 0 \
    --fit off \
    --reasoning off \
    --threads 8 \
    --poll 50 \
    --ctx-size 8192 \
    --parallel 1 \
    --metrics \
    --host "${QWEN36_HOST}" \
    --port "${QWEN36_PORT}"
