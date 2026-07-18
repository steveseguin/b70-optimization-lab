#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
python="${DEEPSEEK_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}"
kernel_tree="${KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc}"
oneccl="${ONECCL_INSTALL_DIR:-/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f}"
corpus="${CORPUS:-/mnt/fast-ai/deepseek-v4-corpora/mtp1-m2-cycle-20260717T0710Z}"
width="${1:?usage: run-mwidth-cycle-gate.sh 4|8 [run-dir]}"
source_width="${SOURCE_WIDTH:-2}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${2:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m${width}-real-cycle-gate-${stamp}}"

case "${width}" in
  4|8) ;;
  *) echo "width must be 4 or 8" >&2; exit 2 ;;
esac
test -x "${python}"
test -d "${kernel_tree}"
test -d "${corpus}"
test -f "${oneccl}/lib/libccl.so.1.0"
test -f "${kernel_tree}/vllm_xpu_kernels/_xpu_C.abi3.so"
mkdir -p "${run_dir}"

set +u
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/mkl/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/dnnl/2025.3/env/vars.sh --force >/dev/null 2>&1
set -u

venv_root="$(dirname "$(dirname "${python}")")"
export PYTHONPATH="${kernel_tree}:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="${oneccl}/lib:${venv_root}/lib:${LD_LIBRARY_PATH:-}"
export LD_PRELOAD="${oneccl}/lib/libccl.so.1.0${LD_PRELOAD:+:${LD_PRELOAD}}"
export CCL_ROOT="${oneccl}"
export CCL_ATL_TRANSPORT=ofi
export CCL_TOPO_P2P_ACCESS=1
export CCL_SYCL_ALLREDUCE_LL="${CCL_SYCL_ALLREDUCE_LL:-ring}"
export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096
export CCL_SYCL_ALLREDUCE_ARC=0
export B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072
export CCL_KERNEL_PATH="${oneccl}/lib/ccl/kernels"
export FI_TCP_IFACE="${FI_TCP_IFACE:-eno1}"
export CCL_KVS_IFACE="${CCL_KVS_IFACE:-eno1}"
export ONEAPI_DEVICE_SELECTOR=level_zero:*
export ZE_AFFINITY_MASK=0,1,2,3
unset CCL_ZE_IPC_EXCHANGE CCL_WORKER_COUNT

{
  printf 'classification=deepseek_v4_row_tiled_mwidth_cycle_gate\n'
  printf 'width=%s\n' "${width}"
  printf 'kernel_commit=%s\n' "$(git -C "${kernel_tree}" rev-parse HEAD)"
  printf 'kernel_diff_sha256=%s\n' "$(git -C "${kernel_tree}" diff --binary | sha256sum | cut -d' ' -f1)"
  printf 'xpu_extension_sha256=%s\n' "$(sha256sum "${kernel_tree}/vllm_xpu_kernels/_xpu_C.abi3.so" | cut -d' ' -f1)"
  printf 'oneccl_libccl_sha256=%s\n' "$(sha256sum "${oneccl}/lib/libccl.so.1.0" | cut -d' ' -f1)"
  printf 'b70_oneccl_sycl_allreduce_max_bytes=%s\n' "${B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES}"
  printf 'ccl_sycl_allreduce_ll=%s\n' "${CCL_SYCL_ALLREDUCE_LL}"
  printf 'corpus=%s\n' "${corpus}"
  printf 'source_width=%s\n' "${source_width}"
} >"${run_dir}/identity.txt"

default_paths="segmented_m2 segmented_fixed_width m2_chunks fixed_width generic_fused"
read -r -a paths <<<"${MWIDTH_PATHS:-${default_paths}}"
for path in "${paths[@]}"; do
  "${python}" -m torch.distributed.run --standalone --nproc_per_node=4 \
    "${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/benchmark-mwidth-cycle-corpus.py" \
    "${corpus}" \
    --width "${width}" \
    --source-width "${source_width}" \
    --path "${path}" \
    --output "${run_dir}/${path}.json" \
    --diagnostic \
    2>&1 | tee -a "${run_dir}/run.log"
done

if [[ "${paths[*]}" == "${default_paths}" ]]; then
  "${python}" \
    "${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/summarize-mwidth-cycle-gate.py" \
    "${run_dir}" \
    --output "${run_dir}/summary.json"
fi
