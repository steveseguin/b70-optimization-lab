#!/usr/bin/env bash
set -euo pipefail

ENTRY_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=runtime-common.sh
source "$ENTRY_DIR/runtime-common.sh"

LLAMA_ROOT=${LLAMA_ROOT:-/mnt/fast-ai/src/llama.cpp-mndodd-4302fb59}
BUILD_DIR=${BUILD_DIR:-$LLAMA_ROOT/build-sycl-aot-bmg-g31}
MODEL=${MODEL:?Set MODEL to the exact Qwen3.6-27B-Q8_0.gguf path}
PORT=${PORT:-18080}
MODEL_SHA256=73f8260284708ed78ae266df672288b6ad1f2c73ec7ffeb7514b5cecdba646c9

printf '%s  %s\n' "$MODEL_SHA256" "$MODEL" | sha256sum --check --status || {
    printf 'Model identity check failed: %s\n' "$MODEL" >&2
    exit 1
}

export ONEAPI_DEVICE_SELECTOR=${ONEAPI_DEVICE_SELECTOR:-level_zero:1}
unset GGML_SYCL_COMM_SINGLE_KERNEL

exec "$BUILD_DIR/bin/llama-server" \
    --model "$MODEL" \
    --device SYCL0 \
    --gpu-layers 99 \
    --split-mode none \
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
    --host 127.0.0.1 \
    --port "$PORT"
