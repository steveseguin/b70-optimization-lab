#!/usr/bin/env bash
set -euo pipefail

vllm_tree="${VLLM_TREE:-/home/steve/src/deepseek-v4-vllm-clean}"
kernel_tree="${XPU_KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-clean}"
python="${DEEPSEEK_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}"

section() {
  printf '\n## %s\n' "$1"
}

section identity
date --iso-8601=seconds
uname -a
lsb_release -ds

section git
git -C "${vllm_tree}" rev-parse HEAD
git -C "${vllm_tree}" status --short --branch
git -C "${kernel_tree}" rev-parse HEAD
git -C "${kernel_tree}" status --short --branch

section storage
df -h / /mnt/fast-ai /mnt/usb-models

section pci
lspci -Dnn | grep -Ei 'VGA|Display|3D'

section xpu_smi
xpu-smi --version
xpu-smi discovery
xpu-smi topology -m

section packages
dpkg-query -W -f='${Package} ${Version}\n' \
  'intel-oneapi-compiler-dpcpp-cpp-*' \
  'intel-oneapi-mkl-devel-*' \
  'intel-oneapi-dnnl-devel-*' \
  'intel-opencl-icd' 'libze-intel-gpu1' 'level-zero' 2>/dev/null | sort || true

section python
"${python}" - <<'PY'
import importlib.metadata as metadata
import torch

for package in (
    "torch",
    "triton-xpu",
    "vllm",
    "vllm-xpu-kernels",
    "intel-sycl-rt",
):
    try:
        print(package, metadata.version(package))
    except metadata.PackageNotFoundError:
        print(package, "missing")
print("torch_xpu_available", torch.xpu.is_available())
print("torch_xpu_devices", torch.xpu.device_count())
for index in range(torch.xpu.device_count()):
    props = torch.xpu.get_device_properties(index)
    print(index, props.name, props.total_memory)
PY
