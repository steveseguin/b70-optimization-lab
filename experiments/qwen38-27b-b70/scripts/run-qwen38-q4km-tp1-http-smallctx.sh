#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
model_dir="${MODEL_DIR:-}"
draft_dir="${DRAFT_DIR:-}"
build_dir="${BUILD_DIR:-}"
source_dir="${SOURCE_DIR:-}"
out_parent="${OUT_DIR:-${repo_root}/experiments/qwen38-27b-b70/data}"
gpu_index="${GPU_INDEX:-0}"
profile="${PROFILE:-tp1}"
topology=tp1
attempt="${ATTEMPT:-1}"
port="${PORT:-18088}"
campaign="${CAMPAIGN_ID:-qwen38-q4km-tp1-http-smallctx-20260825-r1}"
suite="${SUITE_PATH:-${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-smallctx-suite.json}"
prereg="${PREREG_PATH:-${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-smallctx-r1-prereg.json}"
harness_repeats="${HARNESS_REPEATS:-2}"
return_token_ids="${RETURN_TOKEN_IDS:-0}"
api_mode="${API_MODE:-completions}"
disable_prompt_cache="${DISABLE_PROMPT_CACHE:-0}"
oracle_digests="${ORACLE_DIGESTS:-}"
qualification_mode="${QUALIFICATION_MODE:-identity}"
parallel_slots="${PARALLEL_SLOTS:-64}"
ctx_size="${CTX_SIZE:-32768}"
concurrency_points="${CONCURRENCY_POINTS:-1,2,4,8,16,32,64}"
allow_queueing="${ALLOW_QUEUEING:-0}"
concurrent_canary="${CONCURRENT_CANARY:-0}"
canary_concurrency="${CANARY_CONCURRENCY:-64}"
canary_rounds="${CANARY_ROUNDS:-2}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
case "${profile}" in
  tp1)
    model_filename=Qwen3.8-27B-Q4_K_M.gguf
    model_label=qwen38-q4km-tp1-http-smallctx
    expected_model_sha=31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34
    expected_server_sha=35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545
    expected_backend_sha=0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154
    ;;
  q4mtp2_tp1)
    model_filename=Qwen3.8-27B-Q4_K_M.gguf
    model_label=qwen38-q4km-q4mtp-tp1-mtp2-http-smallctx
    expected_model_sha=31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34
    expected_server_sha=35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545
    expected_backend_sha=0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154
    draft_filename=mtp-Qwen3.8-27B-Q4_0.gguf
    expected_draft_sha=50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e
    [[ -n "${draft_dir}" ]] || fail 'q4mtp2_tp1 requires DRAFT_DIR'
    ;;
  tp2)
    topology=tp2
    model_filename=Qwen3.8-27B-Q4_K_M.gguf
    model_label=qwen38-q4km-tp2-http-smallctx
    expected_model_sha=31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34
    expected_server_sha=6ae782c7e8f7a992e0eeced10ade2a84b3cbb9ba65c65cbb917e52d1ce09777d
    expected_backend_sha=375f6d251b022b62367e73d2cd6b7eb0200efc9cc9c854a509af45950938c3ed
    expected_source_commit=a4349bcee933cd2b13820bc72fbe842e9c2f4b7a
    [[ -n "${source_dir}" && -d "${source_dir}/.git" ]] || fail 'TP2 requires SOURCE_DIR'
    ;;
  q8_tp1)
    model_filename=Qwen3.8-27B-Q8_0.gguf
    model_label=qwen38-q8-tp1-http-smallctx
    expected_model_sha=f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8
    expected_server_sha=35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545
    expected_backend_sha=0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154
    ;;
  q8_tp2)
    topology=tp2
    model_filename=Qwen3.8-27B-Q8_0.gguf
    model_label=qwen38-q8-tp2-http-smallctx
    expected_model_sha=f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8
    expected_server_sha=6ae782c7e8f7a992e0eeced10ade2a84b3cbb9ba65c65cbb917e52d1ce09777d
    expected_backend_sha=375f6d251b022b62367e73d2cd6b7eb0200efc9cc9c854a509af45950938c3ed
    expected_source_commit=a4349bcee933cd2b13820bc72fbe842e9c2f4b7a
    [[ -n "${source_dir}" && -d "${source_dir}/.git" ]] || fail 'Q8 TP2 requires SOURCE_DIR'
    ;;
  *) fail 'PROFILE must be tp1, q4mtp2_tp1, tp2, q8_tp1, or q8_tp2' ;;
esac
[[ -n "${model_dir}" && -n "${build_dir}" ]] || fail 'set MODEL_DIR and BUILD_DIR'
[[ "${gpu_index}" =~ ^[0-9]+$ ]] || fail 'GPU_INDEX must be numeric'
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'
[[ "${harness_repeats}" =~ ^[1-9][0-9]*$ ]] || fail 'HARNESS_REPEATS must be positive'
[[ "${return_token_ids}" == 0 || "${return_token_ids}" == 1 ]] || fail 'RETURN_TOKEN_IDS must be 0 or 1'
[[ "${api_mode}" == completions || "${api_mode}" == native ]] || fail 'API_MODE must be completions or native'
[[ "${disable_prompt_cache}" == 0 || "${disable_prompt_cache}" == 1 ]] || fail 'DISABLE_PROMPT_CACHE must be 0 or 1'
[[ "${qualification_mode}" == identity || "${qualification_mode}" == isolation ]] || fail 'QUALIFICATION_MODE must be identity or isolation'
[[ -z "${oracle_digests}" || -f "${oracle_digests}" ]] || fail 'ORACLE_DIGESTS does not exist'
[[ "${parallel_slots}" =~ ^[1-9][0-9]*$ ]] || fail 'PARALLEL_SLOTS must be positive'
[[ "${ctx_size}" =~ ^[1-9][0-9]*$ ]] || fail 'CTX_SIZE must be positive'
[[ "${concurrency_points}" =~ ^[1-9][0-9]*(,[1-9][0-9]*)*$ ]] || fail 'CONCURRENCY_POINTS must be comma-separated positive integers'
[[ "${allow_queueing}" == 0 || "${allow_queueing}" == 1 ]] || fail 'ALLOW_QUEUEING must be 0 or 1'
[[ "${concurrent_canary}" == 0 || "${concurrent_canary}" == 1 ]] || fail 'CONCURRENT_CANARY must be 0 or 1'
[[ "${canary_concurrency}" =~ ^[1-9][0-9]*$ ]] || fail 'CANARY_CONCURRENCY must be positive'
[[ "${canary_rounds}" =~ ^[1-9][0-9]*$ ]] || fail 'CANARY_ROUNDS must be positive'
IFS=, read -r -a concurrency_values <<< "${concurrency_points}"
for value in "${concurrency_values[@]}"; do
  (( allow_queueing == 1 || value <= parallel_slots )) || fail 'a concurrency point exceeds PARALLEL_SLOTS without ALLOW_QUEUEING=1'
done

model="${model_dir}/${model_filename}"
draft=
if [[ -n "${draft_filename:-}" ]]; then draft="${draft_dir}/${draft_filename}"; fi
server="${build_dir}/bin/llama-server"
backend="${build_dir}/bin/libggml-sycl.so"
[[ -f "${model}" && -x "${server}" && -f "${backend}" ]] || fail 'model/server/backend missing'
[[ -z "${draft}" || -f "${draft}" ]] || fail 'draft model missing'
[[ -f "${suite}" && -f "${prereg}" ]] || fail 'frozen preregistration dependency missing'

exec 7>"/run/lock/muse-glimmer-gpu-exclusive.lock"
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>"/tmp/b70-benchmark.lock"
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>"/tmp/b70-gpu${gpu_index}.lock"
flock -n 9 || fail "GPU ${gpu_index} lock is held"
if [[ "${topology}" == tp2 ]]; then
  exec 10>"/tmp/b70-gpu1.lock"
  flock -n 10 || fail 'GPU 1 lock is held'
fi
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'

[[ "$(sha256sum "${model}" | awk '{print $1}')" == "${expected_model_sha}" ]] || fail 'model SHA-256 mismatch'
[[ "$(sha256sum "${server}" | awk '{print $1}')" == "${expected_server_sha}" ]] || fail 'server SHA-256 mismatch'
[[ "$(sha256sum "${backend}" | awk '{print $1}')" == "${expected_backend_sha}" ]] || fail 'backend SHA-256 mismatch'
if [[ -n "${draft}" ]]; then
  [[ "$(sha256sum "${draft}" | awk '{print $1}')" == "${expected_draft_sha}" ]] || fail 'draft SHA-256 mismatch'
fi
if [[ "${topology}" == tp2 ]]; then
  [[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${expected_source_commit}" ]] || fail 'source commit mismatch'
fi

run_dir="${out_parent}/${campaign}-attempt${attempt}"
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
mkdir -p "${run_dir}"
unit="nd-q38-${profile}-p${parallel_slots}-http-a${attempt}"
server_log="${run_dir}/server.log"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
if [[ "${topology}" == tp2 ]]; then
  export ONEAPI_DEVICE_SELECTOR="level_zero:1,0"
  device_args=(--device SYCL0,SYCL1 --split-mode tensor --tensor-split 1,1)
else
  export ONEAPI_DEVICE_SELECTOR="level_zero:${gpu_index}"
  device_args=(--device SYCL0 --split-mode none)
fi
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
sha_inputs=("${model}" "${server}" "${backend}" "${suite}" "${prereg}" "${repo_root}/scripts/bench-openai-concurrency-oracle.py")
if [[ -n "${draft}" ]]; then sha_inputs+=("${draft}"); fi
if (( concurrent_canary == 1 )); then sha_inputs+=("${repo_root}/experiments/qwen38-27b-b70/scripts/qwen38-concurrent-quality-canary.py"); fi
if [[ -n "${oracle_digests}" ]]; then sha_inputs+=("${oracle_digests}"); fi
sha256sum "${sha_inputs[@]}" > "${run_dir}/sha256sums.txt"
if [[ "${topology}" == tp2 ]]; then
  git -C "${source_dir}" status --short > "${run_dir}/source-status.txt"
fi
free -b > "${run_dir}/memory-before.txt"
xpu-smi dump -d "${gpu_index}" -m 0,1,2,3,4,5 -n 1 > "${run_dir}/xpu-before.txt" 2>&1 || true

cmd=("${server}" --model "${model}" "${device_args[@]}" --gpu-layers 99)
if [[ -n "${draft}" ]]; then
  cmd+=(--model-draft "${draft}" --device-draft SYCL0 --gpu-layers-draft 99
    --spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-n-min 0 --spec-draft-p-min 0
    --cache-type-k-draft f16 --cache-type-v-draft f16)
fi
cmd+=(--fit off --flash-attn on --batch-size 2048 --ubatch-size 256
  --cache-type-k f16 --cache-type-v f16 --cache-ram 0 --ctx-checkpoints 0
  --reasoning off --threads 8 --poll 50 --ctx-size "${ctx_size}" --parallel "${parallel_slots}"
  --cont-batching --metrics --host 127.0.0.1 --port "${port}")
if (( disable_prompt_cache == 1 )); then
  cmd+=(--no-cache-prompt --slot-prompt-similarity 0)
fi
printf '%q' "${cmd[0]}" > "${run_dir}/server-command.txt"
printf ' %q' "${cmd[@]:1}" >> "${run_dir}/server-command.txt"
printf '\n' >> "${run_dir}/server-command.txt"

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
  fail "exact ${parallel_slots}-slot profile did not become healthy; retained as unsupported at ${run_dir}"
fi
curl -fsS "http://127.0.0.1:${port}/props" > "${run_dir}/props.json" || true
curl -fsS "http://127.0.0.1:${port}/slots" > "${run_dir}/slots.json" || true

harness_cmd=(python3 "${repo_root}/scripts/bench-openai-concurrency-oracle.py"
  --base-url "http://127.0.0.1:${port}" --model "${model_label}" \
  --api-mode "${api_mode}" --suite "${suite}" --concurrency "${concurrency_points}" \
  --repeats "${harness_repeats}" --max-tokens 128 --seed 42 --timeout 900 \
  --request-extra-json '{"cache_prompt":false,"ignore_eos":true,"temperature":0}' \
  --out "${run_dir}/result.json")
if (( return_token_ids == 1 )); then harness_cmd+=(--return-token-ids); fi
if [[ -n "${oracle_digests}" ]]; then harness_cmd+=(--oracle-digests "${oracle_digests}"); fi
set +e
"${harness_cmd[@]}" | tee "${run_dir}/harness-summary.txt"
harness_status=${PIPESTATUS[0]}
set -e
printf '%s\n' "${harness_status}" > "${run_dir}/harness-exit-status.txt"

python3 -B - "${run_dir}/result.json" "${return_token_ids}" "${qualification_mode}" > "${run_dir}/qualification.json" <<'PY'
import json, sys
path = sys.argv[1]
require_token_ids = sys.argv[2] == "1"
qualification_mode = sys.argv[3]
d = json.load(open(path, encoding="utf-8"))
rows = d["oracle"]["rows"] + [r for b in d["batches"] for r in b["rows"]]
counts_exact = all(r.get("completion_tokens") == 128 for r in rows)
cache_zero = d["oracle"]["cached_tokens_all_zero"] and all(b["cached_tokens_all_zero"] for b in d["batches"])
hashes_exact = all(b["oracle_exact_all"] for b in d["batches"])
token_ids_complete = all(b.get("complete_token_id_identity_all") for b in d["batches"])
cross_base_collisions = sum(b.get("cross_base_oracle_collision_count", 0) for b in d["batches"])
identity_qualified = hashes_exact and d.get("classification") == "output-identity-qualified"
isolation_qualified = d.get("classification") in {
    "output-identity-qualified", "output-isolation-qualified-shape-variant"
} and cross_base_collisions == 0
qualified = counts_exact and cache_zero and (token_ids_complete or not require_token_ids) and (
    identity_qualified if qualification_mode == "identity" else isolation_qualified
)
out = {
    "classification": d.get("classification") if qualified else "measured-output-variant",
    "qualification_mode": qualification_mode,
    "completion_tokens_128_all": counts_exact,
    "cached_tokens_all_zero": cache_zero,
    "oracle_hashes_exact_all": hashes_exact,
    "complete_token_id_identity_all": token_ids_complete,
    "cross_base_oracle_collision_count": cross_base_collisions,
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

if (( concurrent_canary == 1 )); then
  python3 "${repo_root}/experiments/qwen38-27b-b70/scripts/qwen38-concurrent-quality-canary.py" \
    --base-url "http://127.0.0.1:${port}" --model "${model_label}" \
    --concurrency "${canary_concurrency}" --rounds "${canary_rounds}" --timeout 900 \
    --request-id-prefix "${campaign}-a${attempt}-semantic" \
    --output-json "${run_dir}/concurrent-quality-canary.json" \
    >"${run_dir}/concurrent-quality-canary.stdout"
fi

printf 'PASS: %s\n' "${run_dir}"
