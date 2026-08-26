#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "${script_dir}/runtime-common.sh"
source "${script_dir}/config.env"

server="${QWEN38_BUILD_DIR}/bin/llama-server"
parallel_slots="${PARALLEL_SLOTS:-1}"
ctx_size="${CTX_SIZE:-8192}"
threads="${THREADS:-8}"
ubatch_size="${UBATCH_SIZE:-256}"
throughput_mode="${THROUGHPUT_MODE:-0}"
memory_high="${MEMORY_HIGH:-8G}"
memory_max="${MEMORY_MAX:-10G}"
memory_swap_max="${MEMORY_SWAP_MAX:-8G}"
[[ -x "${server}" ]] || { printf 'Missing executable: %s\n' "${server}" >&2; exit 1; }
[[ -f "${QWEN38_MODEL}" ]] || { printf 'Missing model: %s\n' "${QWEN38_MODEL}" >&2; exit 1; }
[[ "${parallel_slots}" =~ ^[1-9][0-9]*$ ]] || { printf 'PARALLEL_SLOTS must be positive\n' >&2; exit 1; }
[[ "${ctx_size}" =~ ^[1-9][0-9]*$ ]] || { printf 'CTX_SIZE must be positive\n' >&2; exit 1; }
[[ "${threads}" =~ ^[1-9][0-9]*$ ]] || { printf 'THREADS must be positive\n' >&2; exit 1; }
[[ "${ubatch_size}" =~ ^[1-9][0-9]*$ ]] || { printf 'UBATCH_SIZE must be positive\n' >&2; exit 1; }
[[ "${throughput_mode}" == 0 || "${throughput_mode}" == 1 ]] || { printf 'THROUGHPUT_MODE must be 0 or 1\n' >&2; exit 1; }

expected_model_sha=f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8
actual_model_sha=$(sha256sum "${QWEN38_MODEL}" | awk '{print $1}')
[[ "${actual_model_sha}" == "${expected_model_sha}" ]] || {
    printf 'Model SHA-256 mismatch: expected %s, got %s\n' "${expected_model_sha}" "${actual_model_sha}" >&2
    exit 1
}

server_args=(
    "${server}" \
    --model "${QWEN38_MODEL}" \
    --device SYCL0,SYCL1 \
    --gpu-layers 99 \
    --split-mode tensor \
    --tensor-split 1,1 \
    --flash-attn on \
    --batch-size 1024 \
    --ubatch-size "${ubatch_size}" \
    --cache-type-k f16 \
    --cache-type-v f16 \
    --cache-ram 0 \
    --ctx-checkpoints 0 \
    --fit off \
    --reasoning off \
    --threads "${threads}" \
    --poll 50 \
    --ctx-size "${ctx_size}" \
    --parallel "${parallel_slots}" \
    --cont-batching \
    --metrics \
    --host "${QWEN38_HOST}" \
    --port "${QWEN38_PORT}"
)
if [[ "${throughput_mode}" == 1 ]]; then
    server_args+=(--no-cache-prompt --slot-prompt-similarity 0)
fi

exec systemd-run --user --scope --quiet \
    --property="MemoryHigh=${memory_high}" \
    --property="MemoryMax=${memory_max}" \
    --property="MemorySwapMax=${memory_swap_max}" \
    "${server_args[@]}"
