#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
benchmark="${script_dir}/benchmark-bf16-allreduce-threshold.py"
python=/home/steve/.venvs/vllm-xpu/bin/python
torchrun=/home/steve/.venvs/vllm-xpu/bin/torchrun
venv=/home/steve/.venvs/vllm-xpu
cmplr_root=/opt/intel/oneapi/compiler/2025.3
libccl="${venv}/lib/libccl.so.1"
libsycl="${venv}/lib/libsycl.so.8"
libfabric="${venv}/lib/libfabric.so.1"
ccl_kernel_path="${venv}/lib/ccl/kernels"

expected_python=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
expected_torchrun=0d8056324b7819d01abb5e07e62286c56cbafec423edde8cf9ab2ae2a719912c
expected_libccl=ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3
expected_libsycl=0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f
expected_libfabric=d849d56fd3f8f2581b4b0c17c1564f8145911a313c2c011d694aaf21e5e86b27
expected_kernels=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9

output_dir=""
trials=3
warmup=50
iterations=500
validate_only=0

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

usage() {
  printf 'Usage: %s --output-dir PATH [--trials 1..5] [--warmup 1..200] [--iterations 20..2000] [--validate-only]\n' "${0##*/}"
}

while (($#)); do
  case "$1" in
    --output-dir) output_dir=${2:?missing output path}; shift 2 ;;
    --trials) trials=${2:?missing trial count}; shift 2 ;;
    --warmup) warmup=${2:?missing warmup count}; shift 2 ;;
    --iterations) iterations=${2:?missing iteration count}; shift 2 ;;
    --validate-only) validate_only=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ -n "${output_dir}" ]] || fail "--output-dir is required"
[[ "${trials}" =~ ^[0-9]+$ ]] && ((trials >= 1 && trials <= 5)) || fail "trials must be in [1,5]"
[[ "${warmup}" =~ ^[0-9]+$ ]] && ((warmup >= 1 && warmup <= 200)) || fail "warmup must be in [1,200]"
[[ "${iterations}" =~ ^[0-9]+$ ]] && ((iterations >= 20 && iterations <= 2000)) || fail "iterations must be in [20,2000]"

for item in "${python}" "${torchrun}" "${benchmark}" "${libccl}" "${libsycl}" "${libfabric}" "${ccl_kernel_path}/kernels.spv"; do
  [[ -f "${item}" ]] || fail "required runtime file is absent: ${item}"
done

check_hash() {
  local path=$1 expected=$2 actual
  actual=$(sha256sum "${path}" | awk '{print $1}')
  [[ "${actual}" == "${expected}" ]] || fail "runtime identity drift for ${path}: ${actual}"
}
check_hash "${python}" "${expected_python}"
check_hash "${torchrun}" "${expected_torchrun}"
check_hash "${libccl}" "${expected_libccl}"
check_hash "${libsycl}" "${expected_libsycl}"
check_hash "${libfabric}" "${expected_libfabric}"
check_hash "${ccl_kernel_path}/kernels.spv" "${expected_kernels}"
"${python}" - "${benchmark}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
compile(path.read_text(encoding="utf-8"), str(path), "exec")
PY

if ((validate_only)); then
  "${python}" - "${output_dir}" "${trials}" "${warmup}" "${iterations}" "${benchmark}" <<'PY'
import hashlib
import json
import pathlib
import sys

output, trials, warmup, iterations, benchmark = sys.argv[1:]
print(json.dumps({
    "status": "validated_not_run",
    "shape": [1, 2560],
    "dtype": "bfloat16",
    "bytes": 5120,
    "thresholds": [4096, 8192],
    "fresh_process_trials_per_arm": int(trials),
    "warmup": int(warmup),
    "iterations": int(iterations),
    "output_dir": str(pathlib.Path(output).resolve()),
    "benchmark_sha256": hashlib.sha256(pathlib.Path(benchmark).read_bytes()).hexdigest(),
}, sort_keys=True))
PY
  exit 0
fi

[[ "${Q38_RUN_BF16_ALLREDUCE_THRESHOLD_AB:-}" == "I_UNDERSTAND_THIS_USES_ALL_FOUR_GPUS" ]] || \
  fail "set Q38_RUN_BF16_ALLREDUCE_THRESHOLD_AB=I_UNDERSTAND_THIS_USES_ALL_FOUR_GPUS"
[[ ! -e "${output_dir}" ]] || fail "refusing to overwrite output path: ${output_dir}"
if pgrep -af '(^|/)(vllm|python)( |.* )serve ' >/dev/null; then
  fail "a model server is running"
fi
mkdir -p "${output_dir}"

summary_paths=()
for trial in $(seq 1 "${trials}"); do
  if ((trial % 2 == 1)); then
    thresholds=(4096 8192)
  else
    thresholds=(8192 4096)
  fi
  for threshold in "${thresholds[@]}"; do
    trial_dir="${output_dir}/${threshold}-trial-${trial}"
    mkdir "${trial_dir}"
    printf '%s trial=%s threshold=%s\n' "$(date --iso-8601=seconds)" "${trial}" "${threshold}" \
      >>"${output_dir}/launch-order.txt"
    timeout --signal=TERM --kill-after=20s 300s env -i \
      HOME=/home/steve \
      PATH="${cmplr_root}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
      LIBRARY_PATH="${cmplr_root}/lib:${cmplr_root}/opt/compiler/lib" \
      LD_LIBRARY_PATH="${venv}/lib:${venv}/lib/python3.12/site-packages/torch/lib:${cmplr_root}/lib:${cmplr_root}/opt/compiler/lib" \
      OCL_ICD_FILENAMES="${cmplr_root}/lib/libintelocl.so" \
      PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
      OMP_NUM_THREADS=1 ZE_AFFINITY_MASK=0,1,2,3 \
      CCL_ATL_TRANSPORT=ofi FI_PROVIDER=tcp FI_TCP_IFACE=lo CCL_KVS_IFACE=lo \
      CCL_ZE_IPC_EXCHANGE=pidfd CCL_SEND=direct CCL_RECV=direct \
      CCL_TOPO_P2P_ACCESS=1 CCL_KERNEL_PATH="${ccl_kernel_path}" \
      CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
      CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
      CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
      CCL_SYCL_ALLREDUCE_LL_THRESHOLD="${threshold}" \
      "${torchrun}" --standalone --nproc-per-node=4 \
      "${benchmark}" rank \
        --output-dir "${trial_dir}" \
        --threshold-bytes "${threshold}" \
        --warmup "${warmup}" \
        --iterations "${iterations}" \
      >"${trial_dir}/torchrun.log" 2>&1
    [[ -s "${trial_dir}/summary.json" ]] || fail "trial summary missing: ${trial_dir}"
    summary_paths+=("${trial_dir}/summary.json")
  done
done

"${python}" "${benchmark}" summarize \
  --output "${output_dir}/comparison.json" \
  "${summary_paths[@]}" \
  >"${output_dir}/comparison.stdout.json"
printf 'PASS: %s\n' "${output_dir}/comparison.json"
