#!/usr/bin/env bash
set -euo pipefail

# Qwen27 TP2 record candidate using the graph-correct public oneCCL build.
# The library is injected only into the vLLM server subprocess; benchmark and
# artifact helpers retain the normal runtime environment.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
QWEN36_27B_AR_VENV="${QWEN36_27B_AR_VENV:-/home/steve/.venvs/vllm-xpu}"
ONECCL_INSTALL_DIR="${ONECCL_INSTALL_DIR:-/mnt/usb-models/llm-runtime/oneccl-4ceafd1-b70}"
ONECCL_LIB="$ONECCL_INSTALL_DIR/lib/libccl.so.1.0"
ONECCL_KERNELS="$ONECCL_INSTALL_DIR/lib/ccl/kernels/kernels.spv"
VALIDATED_LIB_SHA256="43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700"
VALIDATED_KERNELS_SHA256="0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9"

if [[ ! -f "$ONECCL_LIB" || ! -f "$ONECCL_KERNELS" ]]; then
  printf 'oneCCL candidate is missing under %s; build it with %s\n' \
    "$ONECCL_INSTALL_DIR" \
    "$ROOT/experiments/qwen36-27b-autoround-int4-b70/oneccl_ll256/build-public-oneccl.sh" >&2
  exit 2
fi

lib_sha256="$(sha256sum "$ONECCL_LIB" | awk '{print $1}')"
kernels_sha256="$(sha256sum "$ONECCL_KERNELS" | awk '{print $1}')"
if [[ "${ONECCL_ALLOW_UNVALIDATED_BUILD:-0}" != "1" ]] \
  && { [[ "$lib_sha256" != "$VALIDATED_LIB_SHA256" ]] \
    || [[ "$kernels_sha256" != "$VALIDATED_KERNELS_SHA256" ]]; }; then
  printf 'oneCCL checksum is not the validated record build; run the graph oracle or set ONECCL_ALLOW_UNVALIDATED_BUILD=1 for an experiment\n' >&2
  exit 3
fi

export ONECCL_CANDIDATE_PATH="$ONECCL_LIB"
export ONECCL_CANDIDATE_SHA256="$lib_sha256"
export ONECCL_KERNELS_SHA256="$kernels_sha256"
export ONECCL_SOURCE_TOP_COMMIT="b52f40c07f0b140e6aba87548c80720a350a9827"
export ONECCL_LIBCCL_COMMIT="4ceafd15c03ce46f11eeaf91781a92afebd3cecf"
export SERVER_LD_PRELOAD="$ONECCL_LIB"
export SERVER_LD_LIBRARY_PATH="$ONECCL_INSTALL_DIR/lib:$QWEN36_27B_AR_VENV/lib:$QWEN36_27B_AR_VENV/lib/python3.12/site-packages/torch/lib"
export SERVER_CCL_KERNEL_PATH="$ONECCL_INSTALL_DIR/lib/ccl/kernels"
export CCL_LOG_LEVEL="${CCL_LOG_LEVEL:-info}"

exec "$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-targetgraph-drafteager-candidate.sh"
