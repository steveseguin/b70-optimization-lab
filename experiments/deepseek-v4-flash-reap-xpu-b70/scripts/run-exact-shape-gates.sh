#!/usr/bin/env bash
set -euo pipefail

kernel_tree="${XPU_KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-clean}"
python="${DEEPSEEK_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
output_dir="${1:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/stage1-${stamp}}"
test_file="tests/fused_moe/test_fused_moe.py"

mkdir -p "${output_dir}"
set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/mkl/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/dnnl/2025.3/env/vars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR=level_zero:*

{
  printf 'captured_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'kernel_tree=%s\n' "${kernel_tree}"
  printf 'kernel_commit=%s\n' "$(git -C "${kernel_tree}" rev-parse HEAD)"
  printf 'kernel_status=%s\n' "$(git -C "${kernel_tree}" status --porcelain | wc -l)"
  printf 'oneapi_device_selector=%s\n' "${ONEAPI_DEVICE_SELECTOR}"
  "${python}" - <<'PY'
import importlib.metadata as metadata
import torch
for package in ("torch", "triton-xpu", "vllm-xpu-kernels"):
    print(f"package_{package}={metadata.version(package)}")
print(f"xpu_count={torch.xpu.device_count()}")
for index in range(torch.xpu.device_count()):
    print(f"xpu_{index}={torch.xpu.get_device_name(index)}")
PY
} >"${output_dir}/identity.txt"

(
  cd "${kernel_tree}"
  "${python}" -m pytest --collect-only -q \
    "${test_file}::test_deepseek_v4_fused_moe_mxfp4" \
    "${test_file}::test_deepseek_v4_fused_moe_int4_control"
) >"${output_dir}/collected-nodes.txt"

run_case() {
  local device="$1"
  local test_name="$2"
  local experts="$3"
  local label="$4"
  (
    cd "${kernel_tree}"
    local started finished test_rc
    started="$(date +%s)"
    set +e
    ZE_AFFINITY_MASK="${device}" \
      "${python}" -m pytest -q "${test_file}::${test_name}" -k "${experts}" \
      2>&1 | tee "${output_dir}/${label}.log"
    test_rc="${PIPESTATUS[0]}"
    set -e
    finished="$(date +%s)"
    jq -n \
      --arg label "${label}" \
      --arg test "${test_name}" \
      --arg filter "${experts}" \
      --argjson device "${device}" \
      --argjson elapsed_seconds "$((finished - started))" \
      --argjson return_code "${test_rc}" \
      '{label:$label,test:$test,filter:$filter,device:$device,elapsed_seconds:$elapsed_seconds,return_code:$return_code}' \
      >"${output_dir}/${label}.json"
    exit "${test_rc}"
  )
}

run_case 0 test_deepseek_v4_fused_moe_mxfp4 experts40 mxfp4-e40 &
pid0=$!
run_case 1 test_deepseek_v4_fused_moe_mxfp4 experts64 mxfp4-e64 &
pid1=$!
run_case 2 test_deepseek_v4_fused_moe_int4_control experts40 int4-e40 &
pid2=$!
run_case 3 test_deepseek_v4_fused_moe_int4_control experts64 int4-e64 &
pid3=$!

rc=0
for pid in "${pid0}" "${pid1}" "${pid2}" "${pid3}"; do
  wait "${pid}" || rc=1
done

jq -s '{cases:.,passed:(all(.return_code == 0))}' \
  "${output_dir}"/{mxfp4-e40,mxfp4-e64,int4-e40,int4-e64}.json \
  >"${output_dir}/summary.json"
printf 'output_dir=%s\n' "${output_dir}"
exit "${rc}"
