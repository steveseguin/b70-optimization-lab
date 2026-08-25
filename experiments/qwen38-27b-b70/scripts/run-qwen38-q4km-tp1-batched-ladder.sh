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
runtime_profile="${RUNTIME_PROFILE:-control}"
npl="${NPL:-1,2,4,8,16,32,64}"
ctx_size="${CTX_SIZE:-32768}"

campaign="${CAMPAIGN_ID:-qwen38-q4km-tp1-batched-ladder-20260825-r1}"
expected_model_sha=31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34
expected_source_rev=4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126
expected_diff_sha="${EXPECTED_DIFF_SHA:-f24d58bfddb12e7263c2b6974ce8fe2114b47d831f57fe329207ec0edb2f705e}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -n "${model_dir}" && -n "${source_dir}" && -n "${build_dir}" ]] || \
  fail 'set MODEL_DIR, SOURCE_DIR, and BUILD_DIR explicitly'
[[ "${gpu_index}" =~ ^[0-9]+$ ]] || fail 'GPU_INDEX must be numeric'
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'
[[ "${campaign}" =~ ^[a-z0-9][a-z0-9-]*$ ]] || fail 'invalid CAMPAIGN_ID'
[[ "${npl}" =~ ^[1-9][0-9]*(,[1-9][0-9]*)*$ ]] || fail 'invalid NPL list'
[[ "${ctx_size}" =~ ^[1-9][0-9]*$ ]] || fail 'CTX_SIZE must be positive'
[[ "${expected_diff_sha}" =~ ^[0-9a-f]{64}$ ]] || fail 'EXPECTED_DIFF_SHA must be SHA-256'
[[ "${runtime_profile}" == control || "${runtime_profile}" == wdc-q4k || \
   "${runtime_profile}" == wdc-q4k-r1 || \
   "${runtime_profile}" == wdc-q4k-forced || \
   "${runtime_profile}" == wdc-q4k-scoped || \
   "${runtime_profile}" == wdc-q4k-scoped-noq6 ]] || \
  fail 'invalid RUNTIME_PROFILE'
max_pl=$(tr ',' '\n' <<< "${npl}" | sort -nr | head -1)
(( ctx_size >= max_pl * (128 + 256) )) || \
  fail "CTX_SIZE ${ctx_size} is below the exact ${max_pl}x(128+256) token requirement"

# Take the same host-wide locks used by the other B70 campaigns before any
# process scan.  The per-GPU lock alone does not exclude launchers from older
# lanes, and scanning before locking leaves a post-scan race.
exec 7>"/run/lock/muse-glimmer-gpu-exclusive.lock"
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>"/tmp/b70-benchmark.lock"
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>"/tmp/b70-gpu${gpu_index}.lock"
flock -n 9 || fail "GPU ${gpu_index} lock is held"

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
unset GGML_SYCL_WDC GGML_SYCL_WDC_Q4K GGML_SYCL_REORDER_IN_GEMM
unset GGML_SYCL_FORCE_REORDER GGML_SYCL_FORCE_REORDER_Q4K
unset GGML_SYCL_DISABLE_REORDER_Q6K
if [[ "${runtime_profile}" == wdc-q4k || "${runtime_profile}" == wdc-q4k-r1 || \
      "${runtime_profile}" == wdc-q4k-forced || \
      "${runtime_profile}" == wdc-q4k-scoped || \
      "${runtime_profile}" == wdc-q4k-scoped-noq6 ]]; then
  grep -qx 'GGML_SYCL_DNN:BOOL=ON' "${build_dir}/CMakeCache.txt" || \
    fail 'wdc-q4k requires a GGML_SYCL_DNN=ON build'
  grep -Eq '^CMAKE_CXX_FLAGS:STRING=.*GGML_SYCL_Q4K_NIBBLE_PLANE=1' \
    "${build_dir}/CMakeCache.txt" || \
    fail 'wdc-q4k requires GGML_SYCL_Q4K_NIBBLE_PLANE=1 at compile time'
  export GGML_SYCL_WDC_Q4K=1
  export GGML_SYCL_REORDER_IN_GEMM=1
  if [[ "${runtime_profile}" == wdc-q4k-r1 ]]; then
    # Preserves the failed r1 recipe exactly. FORCE_REORDER is a test hook and
    # made the 1.27B-element q6_K output tensor exceed peak VRAM during reorder.
    export GGML_SYCL_FORCE_REORDER=1
  else
    # The integration branch defaults q8_0 WDC on when this is unset. Keep the
    # amended screen type-pure: the per-type Q4_K door above overrides this.
    export GGML_SYCL_WDC=off
    unset GGML_SYCL_FORCE_REORDER
    if [[ "${runtime_profile}" == wdc-q4k-forced ]]; then
      # Diagnostic only: r2 showed REORDER_IN_GEMM is width-gated and vacuous
      # for this harness. This estimates the opportunity before a type-scoped
      # production reorder fix; it is not itself a shippable runtime profile.
      export GGML_SYCL_FORCE_REORDER=1
    elif [[ "${runtime_profile}" == wdc-q4k-scoped || \
            "${runtime_profile}" == wdc-q4k-scoped-noq6 ]]; then
      export GGML_SYCL_FORCE_REORDER_Q4K=1
      if [[ "${runtime_profile}" == wdc-q4k-scoped-noq6 ]]; then
        export GGML_SYCL_DISABLE_REORDER_Q6K=1
      fi
    fi
  fi
fi
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
  --cache-type-v f16 --ctx-size "${ctx_size}" --batch-size 2048 --ubatch-size 256
  --threads 8 --poll 50 -npp 128 -ntg 256 -npl "${npl}"
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
python3 -B - "${run_dir}/rows.jsonl" "${npl}" "${campaign}" \
  > "${run_dir}/summary.json" <<'PY'
import json
import sys

path = sys.argv[1]
rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
expected = [int(item) for item in sys.argv[2].split(",")]
observed = [row["pl"] for row in rows]
if observed != expected:
    raise SystemExit(f"matrix mismatch: expected {expected}, got {observed}")
for row in rows:
    row["per_sequence_tg"] = row["speed_tg"] / row["pl"]
summary = {
    "campaign_id": sys.argv[3],
    "classification": "raw-engine-mechanism-evidence-only",
    "quality_qualified": False,
    "rows": rows,
}
json.dump(summary, sys.stdout, indent=2)
print()
PY

printf 'PASS: %s\n' "${run_dir}"
