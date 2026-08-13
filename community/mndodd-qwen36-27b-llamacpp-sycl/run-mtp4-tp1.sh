#!/usr/bin/env bash
set -euo pipefail

ENTRY_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=runtime-common.sh
source "$ENTRY_DIR/runtime-common.sh"

LLAMA_ROOT=${LLAMA_ROOT:-/mnt/fast-ai/src/llama.cpp-mndodd-4302fb59}
BUILD_DIR=${BUILD_DIR:-$LLAMA_ROOT/build-sycl-aot-bmg-g31}
MODEL=${MODEL:?Set MODEL to the exact Qwen3.6-27B-Q8_0.gguf path}
DRAFT_MODEL=${DRAFT_MODEL:?Set DRAFT_MODEL to the exact mtp-Qwen3.6-27B-Q8_0.gguf path}
PORT=${PORT:-18082}
MODEL_SHA256=73f8260284708ed78ae266df672288b6ad1f2c73ec7ffeb7514b5cecdba646c9
DRAFT_SHA256=ad3862cef3dc6a3eaa0525a5b9b225f1c9c45b15956a8314a30cfaa0344a1e08

printf '%s  %s\n' "$MODEL_SHA256" "$MODEL" | sha256sum --check --status || exit 1
printf '%s  %s\n' "$DRAFT_SHA256" "$DRAFT_MODEL" | sha256sum --check --status || exit 1

export ONEAPI_DEVICE_SELECTOR=${ONEAPI_DEVICE_SELECTOR:-level_zero:1}
export GGML_SYCL_COMM_SINGLE_KERNEL=0

exec "$BUILD_DIR/bin/llama-server" \
    --model "$MODEL" \
    --device SYCL0 \
    --gpu-layers 99 \
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
    --ctx-size 2048 \
    --parallel 1 \
    --metrics \
    --spec-type draft-mtp \
    --spec-draft-model "$DRAFT_MODEL" \
    --spec-draft-device SYCL0 \
    --spec-draft-ngl all \
    --spec-draft-type-k f16 \
    --spec-draft-type-v f16 \
    --spec-draft-n-max 4 \
    --spec-draft-n-min 0 \
    --spec-draft-p-min 0.0 \
    --host 127.0.0.1 \
    --port "$PORT"
