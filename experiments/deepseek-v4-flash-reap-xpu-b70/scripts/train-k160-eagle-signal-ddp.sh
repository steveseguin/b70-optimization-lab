#!/usr/bin/env bash
set -euo pipefail

root=/home/steve/llm-optimizations
python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
torchrun=/home/steve/.venvs/deepseek-v4-xpu/bin/torchrun
trainer="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/train-k160-eagle-signal-head.py"
oneccl_lib=/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib
venv_lib=/home/steve/.venvs/deepseek-v4-xpu/lib

set +u
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/mkl/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/dnnl/2025.3/env/vars.sh --force >/dev/null 2>&1
set -u

export LD_LIBRARY_PATH="${oneccl_lib}:${venv_lib}:${LD_LIBRARY_PATH:-}"
export CCL_ROOT=/home/steve/.venvs/deepseek-v4-xpu
export CCL_ATL_TRANSPORT=ofi
export CCL_TOPO_P2P_ACCESS=1
export CCL_SYCL_ALLREDUCE_LL=ring
export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096
export CCL_SYCL_ALLREDUCE_ARC=0
export CCL_KERNEL_PATH=/home/steve/.venvs/deepseek-v4-xpu/lib/ccl/kernels
export FI_TCP_IFACE=eno1
export CCL_KVS_IFACE=eno1
export ONEAPI_DEVICE_SELECTOR=level_zero:*
export ZE_AFFINITY_MASK=0,1,2,3
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
unset CCL_ZE_IPC_EXCHANGE
unset CCL_WORKER_COUNT

test -x "${python}"
test -x "${torchrun}"
test -f "${trainer}"

exec "${torchrun}" --standalone --nproc-per-node=4 "${trainer}" train "$@"
