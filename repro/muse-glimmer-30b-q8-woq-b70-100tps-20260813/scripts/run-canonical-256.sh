#!/usr/bin/env bash
set -euo pipefail

set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u

source_root=${LLAMA_CPP_ROOT:-"$HOME/src/llama.cpp-muse-q8-woq-repro"}
binary=${MUSE_BINARY:-"$source_root/build-sycl-b70-aot-bmg-g31/bin/llama-server"}
target=${MUSE_TARGET_MODEL:?set MUSE_TARGET_MODEL to the hash-pinned UD-Q8_K_XL GGUF}
draft=${MUSE_DRAFT_MODEL:?set MUSE_DRAFT_MODEL to the hash-pinned BF16 DFlash GGUF}
out_dir=${1:?usage: $0 NEW_OUTPUT_DIRECTORY}

runner_args=(--binary "$binary" --target "$target" --draft "$draft" --out-dir "$out_dir")
if [[ ${MUSE_REQUIRE_RECORD_BINARY:-0} == 1 ]]; then
    runner_args+=(--require-record-binary)
fi
exec python3 "$(dirname "$0")/run-canonical-256.py" "${runner_args[@]}"
