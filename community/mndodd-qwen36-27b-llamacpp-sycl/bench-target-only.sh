#!/usr/bin/env bash
set -euo pipefail

ENTRY_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=runtime-common.sh
source "$ENTRY_DIR/runtime-common.sh"

LLAMA_ROOT=${LLAMA_ROOT:-/mnt/fast-ai/src/llama.cpp-mndodd-4302fb59}
BUILD_DIR=${BUILD_DIR:-$LLAMA_ROOT/build-sycl-aot-bmg-g31}
MODEL=${MODEL:?Set MODEL to the exact Qwen3.6-27B-Q8_0.gguf path}
GPUS=${GPUS:-2}
REPS=${REPS:-5}
MODEL_SHA256=73f8260284708ed78ae266df672288b6ad1f2c73ec7ffeb7514b5cecdba646c9

printf '%s  %s\n' "$MODEL_SHA256" "$MODEL" | sha256sum --check --status || {
    printf 'Model identity check failed: %s\n' "$MODEL" >&2
    exit 1
}

case "$GPUS" in
    1)
        export ONEAPI_DEVICE_SELECTOR=${ONEAPI_DEVICE_SELECTOR:-level_zero:1}
        unset GGML_SYCL_COMM_SINGLE_KERNEL
        device=SYCL0
        split_args=(-sm none)
        ;;
    2)
        export ONEAPI_DEVICE_SELECTOR=${ONEAPI_DEVICE_SELECTOR:-level_zero:1,0}
        export GGML_SYCL_COMM_SINGLE_KERNEL=1
        device=SYCL0/SYCL1
        split_args=(-sm tensor -ts 1/1)
        ;;
    *)
        printf 'GPUS must be 1 or 2, got: %s\n' "$GPUS" >&2
        exit 2
        ;;
esac

exec "$BUILD_DIR/bin/llama-bench" \
    -m "$MODEL" \
    -p 512 \
    -n 128 \
    -ngl 99 \
    -dev "$device" \
    "${split_args[@]}" \
    -fa 1 \
    -ub 32 \
    -ctk f16 \
    -ctv f16 \
    -t 8 \
    --poll 50 \
    -r "$REPS" \
    -o jsonl
