#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
model_dir="${MODEL_DIR:-}"
source_dir="${SOURCE_DIR:-}"
build_dir="${BUILD_DIR:-}"
out_parent="${OUT_DIR:-${repo_root}/experiments/qwen38-27b-b70/data}"
gpu_index="${GPU_INDEX:-0}"
attempt="${ATTEMPT:-1}"

campaign=qwen38-q4km-tp1-batched-ladder-20260825-r1
expected_model_sha=31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34
expected_source_rev=4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126
expected_diff_sha=f24d58bfddb12e7263c2b6974ce8fe2114b47d831f57fe329207ec0edb2f705e

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -n "${model_dir}" && -n "${source_dir}" && -n "${build_dir}" ]] || \
  fail 'set MODEL_DIR, SOURCE_DIR, and BUILD_DIR explicitly'
[[ "${gpu_index}" =~ ^[0-9]+$ ]] || fail 'GPU_INDEX must be numeric'
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'

model="${model_dir}/Qwen3.8-27B-Q4_K_M.gguf"
bench="${build_dir}/bin/llama-batched-bench"
libsycl_backend="${build_dir}/bin/libggml-sycl.so"
[[ -f "${model}" ]] || fail "missing model: ${model}"
[[ -x "${bench}" ]] || fail "missing executable: ${bench}"
[[ -f "${libsycl_backend}" ]] || fail "missing backend: ${libsycl_backend}"
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${expected_source_rev}" ]] || \
  fail 'source base revision mismatch'
git -C "${source_dir}" diff --check
actual_diff_sha=$(git -C "${source_dir}" diff --binary | sha256sum | awk '{print $1}')
[[ "${actual_diff_sha}" == "${expected_diff_sha}" ]] || \
  fail "applied source diff mismatch: ${actual_diff_sha}"

actual_model_sha=$(sha256sum "${model}" | awk '{print $1}')
[[ "${actual_model_sha}" == "${expected_model_sha}" ]] || \
  fail "model SHA-256 mismatch: ${actual_model_sha}"
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && \
  fail 'another model or benchmark process is running'

mkdir -p "${out_parent}"
run_dir="${out_parent}/${campaign}-attempt${attempt}"
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
mkdir "${run_dir}"
exec 9>"/tmp/b70-gpu${gpu_index}.lock"
flock -n 9 || fail "GPU ${gpu_index} lock is held"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR="level_zero:${gpu_index}"
export UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
export UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1
export GGML_SYCL_COMM_SINGLE_KERNEL=1
export GGML_META_FUSE_ALLREDUCE_ADD=1
export GGML_META_FUSE_ALLREDUCE_ADD_RMS_MUL=1
export GGML_SYCL_COMM_FUSED_Q8=1
export GGML_SYCL_FUSED_SWIGLU_Q8=1
export GGML_SYCL_FUSED_ATTN_Q8=1
export GGML_SYCL_FUSED_GDN_Q8=1
export GGML_SYCL_FUSED_MMVQ_PAIR=1
export GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K=1
export GGML_SYCL_FUSED_MMVQ_PAIR_GDN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_ATTN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_GDN=1
export GGML_SYCL_FUSED_MMVQ_QUAD_GDN=1
export GGML_SYCL_FUSED_GDN_BETA_SIGMOID=1
export GGML_SYCL_FUSED_CONCAT_STATE=1
export GGML_SYCL_FUSED_GDN_STATE_IO=1
export GGML_SYCL_FUSED_CONV_STATE_IO=1
export GGML_SYCL_COMM_DIRECT_Q8=2
export GGML_SYCL_FUSED_ROPE_SET_ROWS=1
export GGML_SYCL_COMM_REDUCE_VEC4=1
export GGML_SYCL_FUSED_QK_NORM_ROPE=1
export GGML_SYCL_FUSED_CONV_SILU_L2=1
export GGML_SYCL_FUSE_EXT=31
export GGML_SYCL_QDEDUP_STATS=1
export GGML_SYCL_MMQ_Q4K_REORDER=1
unset GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K_POISON GGML_SYCL_FUSED_GDN_STATE_IO_POISON
unset GGML_SYCL_FUSED_CONV_STATE_IO_POISON GGML_SYCL_GDN_RMS_TAIL_POISON
unset GGML_SYCL_FUSED_QK_NORM_ROPE_POISON GGML_SYCL_FUSED_CONV_SILU_OUTPUT
unset GGML_SYCL_MMVQ_SG32_OUTPUT_HEAD

env | grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|ONEAPI_ROOT=|LD_LIBRARY_PATH=|PATH=)' \
  | LC_ALL=C sort > "${run_dir}/environment.txt"
uname -a > "${run_dir}/uname.txt"
free -b > "${run_dir}/memory-before.txt"
"${bench}" --version > "${run_dir}/version.txt" 2>&1
sha256sum "${model}" "${bench}" "${libsycl_backend}" > "${run_dir}/sha256sums.txt"
ldd "${bench}" > "${run_dir}/ldd.txt"
xpu-smi discovery -l > "${run_dir}/xpu-discovery.txt" 2>&1 || true
xpu-smi dump -d "${gpu_index}" -m 0,1,2,3,4,5 -n 1 > "${run_dir}/xpu-before.txt" 2>&1 || true

cmd=("${bench}" --model "${model}" --device SYCL0 --gpu-layers 99
  --split-mode none --fit off --flash-attn on --cache-type-k f16
  --cache-type-v f16 --ctx-size 32768 --batch-size 2048 --ubatch-size 256
  --threads 8 --poll 50 -npp 128 -ntg 256 -npl "1,2,4,8,16,32,64"
  --output-format jsonl)
printf '%q ' "${cmd[@]}" > "${run_dir}/command.txt"
printf '\n' >> "${run_dir}/command.txt"

set +e
systemd-run --user --scope --quiet --collect \
  -p MemoryHigh=11G -p MemoryMax=13G -p MemorySwapMax=12G \
  timeout --signal=TERM --kill-after=30 7200 "${cmd[@]}" \
  2>&1 | tee "${run_dir}/raw.log"
status=${PIPESTATUS[0]}
set -e
printf '%s\n' "${status}" > "${run_dir}/exit-status.txt"
xpu-smi dump -d "${gpu_index}" -m 0,1,2,3,4,5 -n 1 > "${run_dir}/xpu-after.txt" 2>&1 || true
free -b > "${run_dir}/memory-after.txt"
(( status == 0 )) || fail "benchmark exited ${status}; raw evidence retained at ${run_dir}"

awk '/^\{.*"speed_tg"/ { print }' "${run_dir}/raw.log" > "${run_dir}/rows.jsonl"
python3 -B - "${run_dir}/rows.jsonl" > "${run_dir}/summary.json" <<'PY'
import json
import sys

path = sys.argv[1]
rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
expected = [1, 2, 4, 8, 16, 32, 64]
observed = [row["pl"] for row in rows]
if observed != expected:
    raise SystemExit(f"matrix mismatch: expected {expected}, got {observed}")
for row in rows:
    row["per_sequence_tg"] = row["speed_tg"] / row["pl"]
summary = {
    "campaign_id": "qwen38-q4km-tp1-batched-ladder-20260825-r1",
    "classification": "raw-engine-mechanism-evidence-only",
    "quality_qualified": False,
    "rows": rows,
}
json.dump(summary, sys.stdout, indent=2)
print()
PY

printf 'PASS: %s\n' "${run_dir}"
