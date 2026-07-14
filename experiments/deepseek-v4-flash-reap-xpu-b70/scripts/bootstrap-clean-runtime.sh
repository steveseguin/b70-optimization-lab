#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
uv="${UV_BIN:-/home/steve/.local/bin/uv}"
venv="${DEEPSEEK_VENV:-/home/steve/.venvs/deepseek-v4-xpu}"
python="${venv}/bin/python"
vllm_tree="${VLLM_TREE:-/home/steve/src/deepseek-v4-vllm-clean}"
kernel_tree="${KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-clean}"
vllm_commit="382bbd51448b2f58c73b3e51d051bc352166ba91"
kernel_commit="840482d03ee12f6398967757efee9a493225644d"

test -x "${uv}"
test -d /opt/intel/oneapi/compiler/2025.3
test -d /opt/intel/oneapi/mkl/2025.3
test -d /opt/intel/oneapi/dnnl/2025.3
test "$(git -C "${vllm_tree}" rev-parse HEAD)" = "${vllm_commit}"
test "$(git -C "${kernel_tree}" rev-parse HEAD)" = "${kernel_commit}"
test -z "$(git -C "${vllm_tree}" status --porcelain)"
test -z "$(git -C "${kernel_tree}" status --porcelain)"

if [[ ! -x "${python}" ]]; then
  "${uv}" venv --python 3.12 "${venv}"
fi

# Resolve the pinned vLLM XPU dependency set without downloading the released
# kernel wheel; the exact source-built kernel is installed last by the builder.
filtered_requirements="$(mktemp "${vllm_tree}/requirements/deepseek-xpu.XXXXXX.txt")"
trap 'rm -f "${filtered_requirements}"' EXIT
sed '/^vllm_xpu_kernels @/d' "${vllm_tree}/requirements/xpu.txt" \
  >"${filtered_requirements}"
"${uv}" pip install --python "${python}" -r "${filtered_requirements}"
"${uv}" pip install --python "${python}" -r "${kernel_tree}/requirements.txt"

# Prevent a generic CUDA Triton package from shadowing the XPU build, then pin
# the critical packages whose ABI/version is part of the Stage-0 identity.
"${uv}" pip uninstall --python "${python}" triton >/dev/null 2>&1 || true
"${uv}" pip install --python "${python}" \
  'setuptools==79.0.1' 'triton-xpu==3.7.1' 'pytest==9.0.2'
rm -f "${filtered_requirements}"
trap - EXIT

DEEPSEEK_PYTHON="${python}" VLLM_TREE="${vllm_tree}" \
  KERNEL_TREE="${kernel_tree}" \
  "${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/build-clean-runtime.sh"
