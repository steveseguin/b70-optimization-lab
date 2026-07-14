#!/usr/bin/env bash
set -euo pipefail

python="${DEEPSEEK_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}"
uv="${UV_BIN:-/home/steve/.local/bin/uv}"
kernel_tree="${KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-clean}"
vllm_tree="${VLLM_TREE:-/home/steve/src/deepseek-v4-vllm-clean}"
kernel_commit="840482d03ee12f6398967757efee9a493225644d"
vllm_commit="382bbd51448b2f58c73b3e51d051bc352166ba91"

test -x "${python}"
test -x "${uv}"
test "$(git -C "${kernel_tree}" rev-parse HEAD)" = "${kernel_commit}"
test "$(git -C "${vllm_tree}" rev-parse HEAD)" = "${vllm_commit}"
test -z "$(git -C "${kernel_tree}" status --porcelain)"
test -z "$(git -C "${vllm_tree}" status --porcelain)"

set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/mkl/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/dnnl/2025.3/env/vars.sh --force >/dev/null 2>&1
set -u

export VLLM_TARGET_DEVICE=xpu
export BUILD_SYCL_TLA_KERNELS=ON
export VLLM_XPU_ENABLE_XE2=ON
export VLLM_XPU_ENABLE_XE_DEFAULT=ON
export MAX_JOBS="${MAX_JOBS:-8}"
export VLLM_PAGED_DECODE_CONFIG="${VLLM_PAGED_DECODE_CONFIG:-paged_decode_default.conf}"
export VLLM_CHUNK_PREFILL_CONFIG="${VLLM_CHUNK_PREFILL_CONFIG:-chunk_prefill_default.conf}"

# The environment bootstrap owns dependencies. Keep both editable installs
# no-deps so vLLM cannot download and substitute the released kernel wheel.
"${uv}" pip install --python "${python}" --no-build-isolation --no-deps \
  -e "${vllm_tree}" -v
"${uv}" pip install --python "${python}" --no-build-isolation --no-deps \
  -e "${kernel_tree}" -v

KERNEL_TREE="${kernel_tree}" VLLM_TREE="${vllm_tree}" "${python}" - <<'PY'
import importlib.metadata
import os
import pathlib

import torch
import triton
import vllm
import vllm_xpu_kernels

print("torch", torch.__version__)
print("triton", triton.__version__)
print("vllm", importlib.metadata.version("vllm"), pathlib.Path(vllm.__file__).resolve())
print(
    "vllm_xpu_kernels",
    importlib.metadata.version("vllm-xpu-kernels"),
    pathlib.Path(vllm_xpu_kernels.__file__).resolve(),
)
print("xpu_count", torch.xpu.device_count())
assert torch.__version__.startswith("2.12.0+xpu")
assert triton.__version__ == "3.7.1"
assert torch.xpu.device_count() == 4
assert pathlib.Path(vllm.__file__).resolve().is_relative_to(
    pathlib.Path(os.environ["VLLM_TREE"]).resolve()
)
assert pathlib.Path(vllm_xpu_kernels.__file__).resolve().is_relative_to(
    pathlib.Path(os.environ["KERNEL_TREE"]).resolve()
)
PY
