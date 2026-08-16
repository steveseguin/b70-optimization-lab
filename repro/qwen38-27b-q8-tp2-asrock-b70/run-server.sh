#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "${script_dir}/runtime-common.sh"
source "${script_dir}/config.env"

server="${QWEN38_BUILD_DIR}/bin/llama-server"
[[ -x "${server}" ]] || { printf 'Missing executable: %s\n' "${server}" >&2; exit 1; }
[[ -f "${QWEN38_MODEL}" ]] || { printf 'Missing model: %s\n' "${QWEN38_MODEL}" >&2; exit 1; }

expected_model_sha=f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8
actual_model_sha=$(sha256sum "${QWEN38_MODEL}" | awk '{print $1}')
[[ "${actual_model_sha}" == "${expected_model_sha}" ]] || {
    printf 'Model SHA-256 mismatch: expected %s, got %s\n' "${expected_model_sha}" "${actual_model_sha}" >&2
    exit 1
}

exec systemd-run --user --scope --quiet \
    --property=MemoryHigh=8G \
    --property=MemoryMax=10G \
    --property=MemorySwapMax=8G \
    "${server}" \
    --model "${QWEN38_MODEL}" \
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
    --host "${QWEN38_HOST}" \
    --port "${QWEN38_PORT}"
