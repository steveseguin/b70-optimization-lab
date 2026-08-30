#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
arm=${ARM:?set ARM to control or candidate}
attempt=${ATTEMPT:-1}
model_dir=${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-gguf}
source_dir=${SOURCE_DIR:-/media/steve/extended-ssd/steve-archive/active-qwen38-tp1-concurrency-20260825}
build_dir=${BUILD_DIR:-${source_dir}/build-sycl-aot-bmg-g31-wdc-noq6-r5}
out_parent=${OUT_DIR:-/mnt/fast-ai/bench-results}
campaign=qwen38-q4km-tp2-wdc-feasibility-20260830-r1
run_dir=${out_parent}/${campaign}-${arm}-attempt${attempt}
model=${model_dir}/Qwen3.8-27B-Q4_K_M.gguf
bench=${build_dir}/bin/llama-batched-bench
backend=${build_dir}/bin/libggml-sycl.so.0.19.0
bench_impl=${build_dir}/bin/libllama-batched-bench-impl.so
libllama=${build_dir}/bin/libllama.so.0.1.0
libggml=${build_dir}/bin/libggml.so.0.19.0
libbase=${build_dir}/bin/libggml-base.so.0.19.0
libcpu=${build_dir}/bin/libggml-cpu.so.0.19.0
prereg=${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-wdc-feasibility-r1-prereg.json

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
case ${arm} in control|candidate) ;; *) fail 'ARM must be control or candidate' ;; esac
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
[[ "$(findmnt -no FSTYPE --target "${out_parent}")" == ext4 ]] || fail 'OUT_DIR must be on ext4'

check_hash() {
  local expected=$1 path=$2 actual
  [[ -f "${path}" ]] || fail "missing ${path}"
  actual=$(sha256sum "${path}" | awk '{print $1}')
  [[ "${actual}" == "${expected}" ]] || fail "identity mismatch: ${path}"
}
check_hash 31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34 "${model}"
check_hash c2d55d3c7d55f0f309bc381ca9ca35b0d57193b8d64f8c2fb4bd98e631bd7248 "${bench}"
check_hash 2549cb97c9789a8a70c6f5187119c1bfe73a211b6312fbe396c05e288517cdeb "${backend}"
check_hash 4a7094e725a42c8425dbd5f48b2fd9c5e4dc7a5e84044801e7db10d879fbe5d6 "${bench_impl}"
check_hash fef127ab3ce7fa5d530ca641a4e618622ddda31c9d765b0efb7557742b7ed291 "${libllama}"
check_hash d81df5455db5a4c28452b82ed88149fa0e0b2cfef19191d4da0751de5875db4e "${libggml}"
check_hash 86ba1569de3f0222b8939f518eac3a04a9c4285deb42184cb7f7159ca4e774b0 "${libbase}"
check_hash 14a864bb492541497ba201a6c8c2a7b0c3dee7ae19eb7f4eab18170ec9bc99ab "${libcpu}"
[[ -f "${prereg}" ]] || fail "missing ${prereg}"
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126 ]] || fail 'source commit mismatch'
[[ "$(git -C "${source_dir}" diff --binary | sha256sum | awk '{print $1}')" == 6a6b49a22e09738f5de7bd04f1ac71b4a39d764091c5cf4f02ee0c526dce170f ]] || fail 'source diff mismatch'

exec 7>/run/lock/muse-glimmer-gpu-exclusive.lock
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>/tmp/b70-gpu0.lock
flock -n 9 || fail 'GPU 0 lock is held'
exec 10>/tmp/b70-gpu1.lock
flock -n 10 || fail 'GPU 1 lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'

mkdir -p "${run_dir}"
date -u +%Y-%m-%dT%H:%M:%SZ >"${run_dir}/start-utc.txt"
sha256sum "${model}" "${bench}" "${backend}" "${bench_impl}" "${libllama}" \
  "${libggml}" "${libbase}" "${libcpu}" "${prereg}" "${BASH_SOURCE[0]}" \
  >"${run_dir}/input-sha256sums.txt"
git -C "${source_dir}" diff --binary >"${run_dir}/source.diff"
git -C "${source_dir}" status --short >"${run_dir}/source-status.txt"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export LD_LIBRARY_PATH="${build_dir}/bin${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export ONEAPI_DEVICE_SELECTOR=level_zero:1,0
export UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
export UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1
export GGML_SYCL_ENABLE_GRAPH=0
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
export GGML_SYCL_WDC=off
export GGML_SYCL_REORDER_IN_GEMM=1
export GGML_SYCL_FORCE_REORDER_Q4K=1
export GGML_SYCL_DISABLE_REORDER_Q6K=1
unset GGML_SYCL_FORCE_REORDER
if [[ "${arm}" == candidate ]]; then
  export GGML_SYCL_WDC_Q4K=1
else
  export GGML_SYCL_WDC_Q4K=0
fi

env | grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|ONEAPI_ROOT=|LD_LIBRARY_PATH=)' |
  LC_ALL=C sort >"${run_dir}/runtime-environment.txt"
free -b >"${run_dir}/memory-before.txt"
for device in 0 1; do
  xpu-smi dump --device "${device}" --metrics MEMORY,POWER --number 1 >"${run_dir}/xpu-before-${device}.txt" 2>&1 || true
done

cmd=("${bench}" --model "${model}" --device SYCL0,SYCL1 --gpu-layers 99
  --split-mode tensor --tensor-split 1,1 --fit off --flash-attn on
  --cache-type-k f16 --cache-type-v f16 --ctx-size 32768
  --batch-size 2048 --ubatch-size 256 --threads 8 --poll 50
  -npp 128 -ntg 128 -npl 64 --output-format jsonl)
printf '%q ' "${cmd[@]}" >"${run_dir}/command.txt"
printf '\n' >>"${run_dir}/command.txt"

set +e
systemd-run --user --scope --quiet --collect \
  -p MemoryHigh=11G -p MemoryMax=13G -p MemorySwapMax=12G \
  timeout --signal=TERM --kill-after=30 3600 "${cmd[@]}" \
  >"${run_dir}/raw.log" 2>&1
status=$?
set -e
printf '%s\n' "${status}" >"${run_dir}/exit-status.txt"
for device in 0 1; do
  xpu-smi dump --device "${device}" --metrics MEMORY,POWER --number 1 >"${run_dir}/xpu-after-${device}.txt" 2>&1 || true
done
free -b >"${run_dir}/memory-after.txt"
start=$(cat "${run_dir}/start-utc.txt")
journalctl -k -b --since "${start}" --no-pager |
  grep -Ei 'llama-batched-bench.*segfault|xe.*(fault|reset|hang)|device lost|CAT fault|oom|out of memory' \
  >"${run_dir}/kernel-errors.txt" || true
(( status == 0 )) || fail "benchmark exited ${status}; retained at ${run_dir}"
[[ ! -s "${run_dir}/kernel-errors.txt" ]] || fail "kernel error evidence retained at ${run_dir}"

awk '/^\{.*"speed_tg"/ { print }' "${run_dir}/raw.log" >"${run_dir}/rows.jsonl"
python3 - "${run_dir}" "${arm}" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
arm = sys.argv[2]
rows = [json.loads(line) for line in open(root / "rows.jsonl") if line.strip()]
if len(rows) != 1 or rows[0].get("pl") != 64:
    raise SystemExit(f"expected exactly one pl=64 row, got {rows}")
text = (root / "raw.log").read_text(errors="replace")
banner_on = "SYCL doors | WDC q4_K   : on" in text
banner_off = "SYCL doors | WDC q4_K   : off" in text
engaged = "weight-decompression GEMM ENGAGED" in text
if arm == "candidate" and not (banner_on and engaged):
    raise SystemExit("candidate WDC liveness failed")
if arm == "control" and not (banner_off and not engaged):
    raise SystemExit("control WDC liveness failed")
summary = {
    "classification": "raw-engine-mechanism-evidence-only",
    "quality_qualified": False,
    "arm": arm,
    "row": rows[0],
    "aggregate_speed_tg": rows[0]["speed_tg"],
    "wdc_banner_on": banner_on,
    "wdc_banner_off": banner_off,
    "wdc_engaged": engaged,
    "kernel_errors_zero": True,
}
json.dump(summary, open(root / "summary.json", "w"), indent=2)
print(json.dumps(summary, indent=2))
PY

printf 'PASS: %s\n' "${run_dir}"
