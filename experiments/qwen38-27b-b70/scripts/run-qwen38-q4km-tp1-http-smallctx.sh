#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
model_dir="${MODEL_DIR:-}"
build_dir="${BUILD_DIR:-}"
out_parent="${OUT_DIR:-${repo_root}/experiments/qwen38-27b-b70/data}"
gpu_index="${GPU_INDEX:-0}"
attempt="${ATTEMPT:-1}"
port="${PORT:-18088}"
campaign="qwen38-q4km-tp1-http-smallctx-20260825-r1"
suite="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-smallctx-suite.json"
prereg="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-smallctx-r1-prereg.json"
expected_model_sha=31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34
expected_server_sha=35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545
expected_backend_sha=0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -n "${model_dir}" && -n "${build_dir}" ]] || fail 'set MODEL_DIR and BUILD_DIR'
[[ "${gpu_index}" =~ ^[0-9]+$ ]] || fail 'GPU_INDEX must be numeric'
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'

model="${model_dir}/Qwen3.8-27B-Q4_K_M.gguf"
server="${build_dir}/bin/llama-server"
backend="${build_dir}/bin/libggml-sycl.so"
[[ -f "${model}" && -x "${server}" && -f "${backend}" ]] || fail 'model/server/backend missing'
[[ -f "${suite}" && -f "${prereg}" ]] || fail 'frozen preregistration dependency missing'

exec 7>"/run/lock/muse-glimmer-gpu-exclusive.lock"
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>"/tmp/b70-benchmark.lock"
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>"/tmp/b70-gpu${gpu_index}.lock"
flock -n 9 || fail "GPU ${gpu_index} lock is held"
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'

[[ "$(sha256sum "${model}" | awk '{print $1}')" == "${expected_model_sha}" ]] || fail 'model SHA-256 mismatch'
[[ "$(sha256sum "${server}" | awk '{print $1}')" == "${expected_server_sha}" ]] || fail 'server SHA-256 mismatch'
[[ "$(sha256sum "${backend}" | awk '{print $1}')" == "${expected_backend_sha}" ]] || fail 'backend SHA-256 mismatch'

run_dir="${out_parent}/${campaign}-attempt${attempt}"
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
mkdir -p "${run_dir}"
unit="nd-q38-http-smallctx-a${attempt}"
server_log="${run_dir}/server.log"

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
unset GGML_SYCL_FORCE_REORDER GGML_SYCL_FORCE_REORDER_Q4K GGML_SYCL_DISABLE_REORDER_Q6K

env | grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|ONEAPI_ROOT=|LD_LIBRARY_PATH=|PATH=)' | LC_ALL=C sort > "${run_dir}/environment.txt"
sha256sum "${model}" "${server}" "${backend}" "${suite}" "${prereg}" "${repo_root}/scripts/bench-openai-concurrency-oracle.py" > "${run_dir}/sha256sums.txt"
free -b > "${run_dir}/memory-before.txt"
xpu-smi dump -d "${gpu_index}" -m 0,1,2,3,4,5 -n 1 > "${run_dir}/xpu-before.txt" 2>&1 || true

cmd=("${server}" --model "${model}" --device SYCL0 --gpu-layers 99
  --split-mode none --fit off --flash-attn on --batch-size 2048 --ubatch-size 256
  --cache-type-k f16 --cache-type-v f16 --cache-ram 0 --ctx-checkpoints 0
  --reasoning off --threads 8 --poll 50 --ctx-size 32768 --parallel 64
  --cont-batching --metrics --host 127.0.0.1 --port "${port}")
printf '%q ' "${cmd[@]}" > "${run_dir}/server-command.txt"; printf '\n' >> "${run_dir}/server-command.txt"

cleanup() {
  # Signal only timeout, which forwards one TERM to the server. Stopping the
  # whole scope first signals both timeout and its child and made this runtime
  # treat cleanup as a double interrupt after otherwise complete evidence.
  if [[ -n "${server_pid:-}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill -TERM "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  systemctl --user stop "${unit}.scope" >/dev/null 2>&1 || true
  free -b > "${run_dir}/memory-after.txt" 2>/dev/null || true
  xpu-smi dump -d "${gpu_index}" -m 0,1,2,3,4,5 -n 1 > "${run_dir}/xpu-after.txt" 2>&1 || true
}
trap cleanup EXIT INT TERM

set +e
systemd-run --user --scope --quiet --collect --unit="${unit}" \
  -p MemoryHigh=11G -p MemoryMax=13G -p MemorySwapMax=12G \
  timeout --signal=TERM --kill-after=30 3600 "${cmd[@]}" >"${server_log}" 2>&1 &
server_pid=$!
set -e

healthy=0
for _ in $(seq 1 360); do
  if curl -fsS "http://127.0.0.1:${port}/health" > "${run_dir}/health.json" 2>/dev/null; then healthy=1; break; fi
  if ! kill -0 "${server_pid}" 2>/dev/null; then break; fi
  sleep 1
done
if (( healthy == 0 )); then
  wait "${server_pid}" || status=$?
  printf '%s\n' "${status:-1}" > "${run_dir}/server-exit-status.txt"
  fail "exact 64-slot profile did not become healthy; retained as unsupported at ${run_dir}"
fi
curl -fsS "http://127.0.0.1:${port}/props" > "${run_dir}/props.json" || true
curl -fsS "http://127.0.0.1:${port}/slots" > "${run_dir}/slots.json" || true

set +e
python3 "${repo_root}/scripts/bench-openai-concurrency-oracle.py" \
  --base-url "http://127.0.0.1:${port}" --model qwen38-q4km-tp1-http-smallctx \
  --api-mode completions --suite "${suite}" --concurrency 1,2,4,8,16,32,64 \
  --repeats 2 --max-tokens 128 --seed 42 --timeout 900 \
  --request-extra-json '{"cache_prompt":false,"ignore_eos":true,"temperature":0}' \
  --out "${run_dir}/result.json" | tee "${run_dir}/harness-summary.txt"
harness_status=${PIPESTATUS[0]}
set -e
printf '%s\n' "${harness_status}" > "${run_dir}/harness-exit-status.txt"

python3 -B - "${run_dir}/result.json" > "${run_dir}/qualification.json" <<'PY'
import json, sys
path = sys.argv[1]
d = json.load(open(path, encoding="utf-8"))
rows = d["oracle"]["rows"] + [r for b in d["batches"] for r in b["rows"]]
counts_exact = all(r.get("completion_tokens") == 128 for r in rows)
cache_zero = d["oracle"]["cached_tokens_all_zero"] and all(b["cached_tokens_all_zero"] for b in d["batches"])
hashes_exact = all(b["oracle_exact_all"] for b in d["batches"])
qualified = counts_exact and cache_zero and hashes_exact and d.get("classification") == "output-identity-qualified"
out = {
    "classification": "output-identity-qualified" if qualified else "measured-output-variant",
    "completion_tokens_128_all": counts_exact,
    "cached_tokens_all_zero": cache_zero,
    "oracle_hashes_exact_all": hashes_exact,
    "request_count": len(rows),
    "batches": [{
        "concurrency": b["concurrency"], "repeat": b["repeat"],
        "aggregate_tok_s_wall": b["aggregate_tok_s_wall"],
        "per_user_tok_s_wall": b["aggregate_tok_s_wall"] / b["concurrency"],
        "oracle_exact": f"{b['oracle_exact_count']}/{b['oracle_exact_total']}"
    } for b in d["batches"]],
}
json.dump(out, sys.stdout, indent=2); print()
if not qualified:
    raise SystemExit(3)
PY

printf 'PASS: %s\n' "${run_dir}"
