#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
target_dir=${TARGET_DIR:?set TARGET_DIR}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR}
build_dir=${BUILD_DIR:?set BUILD_DIR}
depth=${MTP_DEPTH:?set MTP_DEPTH to 0 or 2}
attempt=${ATTEMPT:?set ATTEMPT to a unique label}
out_dir=${OUT_DIR:?set OUT_DIR to a new evidence directory}
port=${PORT:-18145}
parallel_slots=${PARALLEL_SLOTS:-64}
ctx_size=${CTX_SIZE:-32768}
concurrency_points=${CONCURRENCY_POINTS:-1,2,4,8,16,32,64}
prereg=${PREREG:-${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-http-concurrency-r1-prereg.json}
suite=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
oracle=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-concurrency-oracle-digests.json
launcher=${repo}/repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
harness=${repo}/scripts/bench-openai-concurrency-oracle.py
canary=${repo}/experiments/qwen38-27b-b70/scripts/qwen38-concurrent-quality-canary.py

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "${depth}" == 0 || "${depth}" == 2 ]] || fail 'MTP_DEPTH must be 0 or 2'
[[ "${parallel_slots}" =~ ^[1-9][0-9]*$ ]] || fail 'PARALLEL_SLOTS must be positive'
[[ "${ctx_size}" =~ ^[1-9][0-9]*$ ]] || fail 'CTX_SIZE must be positive'
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'
[[ "${attempt}" =~ ^[a-z0-9][a-z0-9._-]*$ ]] || fail 'ATTEMPT must be a lowercase label'
[[ ! -e "${out_dir}" ]] || fail "refusing to overwrite ${out_dir}"
for path in "${prereg}" "${suite}" "${oracle}" "${launcher}" "${harness}" "${canary}"; do
  [[ -f "${path}" ]] || fail "missing dependency ${path}"
done
for value in ${concurrency_points//,/ }; do
  [[ "${value}" =~ ^[1-9][0-9]*$ ]] || fail 'invalid concurrency point'
  (( value <= parallel_slots )) || fail 'concurrency exceeds configured slots'
done

exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'
mkdir -p "${out_dir}"

sha256sum \
  "${target_dir}/Qwen3.8-27B-Q4_K_M.gguf" \
  "${draft_dir}/mtp-Qwen3.8-27B-Q4_0.gguf" \
  "${build_dir}/bin/llama-server" "${build_dir}/bin/libggml-sycl.so" \
  "${prereg}" "${suite}" "${oracle}" "${launcher}" "${harness}" "${canary}" \
  >"${out_dir}/sha256sums.txt"
free -b >"${out_dir}/memory-before.txt"
xpu-smi dump --device 0,1 --metrics MEMORY,POWER --number 1 >"${out_dir}/xpu-before.txt" 2>&1 || true

cleanup() {
  if [[ -n "${server_pid:-}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill -INT "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  local llama_pid
  llama_pid=$(pgrep -n -x llama-server || true)
  if [[ -n "${llama_pid}" ]]; then
    kill -TERM "${llama_pid}" 2>/dev/null || true
    for _ in $(seq 1 60); do
      kill -0 "${llama_pid}" 2>/dev/null || break
      sleep 0.5
    done
  fi
  free -b >"${out_dir}/memory-after.txt" 2>/dev/null || true
  xpu-smi dump --device 0,1 --metrics MEMORY,POWER --number 1 >"${out_dir}/xpu-after.txt" 2>&1 || true
}
trap cleanup EXIT INT TERM

timeout --signal=INT --kill-after=30s 3600s env \
  TARGET_DIR="${target_dir}" DRAFT_DIR="${draft_dir}" BUILD_DIR="${build_dir}" \
  MTP_DEPTH="${depth}" PORT="${port}" CTX_SIZE="${ctx_size}" PARALLEL_SLOTS="${parallel_slots}" \
  BATCH_SIZE=1024 UBATCH_SIZE=256 THREADS=8 \
  "${launcher}" >"${out_dir}/server.log" 2>&1 &
server_pid=$!

healthy=0
for _ in $(seq 1 420); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/health.json" 2>/dev/null; then
    healthy=1
    break
  fi
  kill -0 "${server_pid}" 2>/dev/null || break
  sleep 1
done
if (( healthy == 0 )); then
  wait "${server_pid}" || status=$?
  printf '%s\n' "${status:-1}" >"${out_dir}/server-exit-status.txt"
  fail 'server did not become healthy'
fi

llama_pid=$(pgrep -n -x llama-server || true)
[[ -n "${llama_pid}" ]] || fail 'healthy endpoint has no llama-server process'
tr '\0' ' ' <"/proc/${llama_pid}/cmdline" >"${out_dir}/server-command.txt"
printf '\n' >>"${out_dir}/server-command.txt"
tr '\0' '\n' <"/proc/${llama_pid}/environ" |
  grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|SYCL_UR_USE_LEVEL_ZERO_V2=|ONEAPI_ROOT=|LD_LIBRARY_PATH=)' |
  LC_ALL=C sort >"${out_dir}/runtime-environment.txt"
curl -fsS "http://127.0.0.1:${port}/props" >"${out_dir}/props.json"
curl -fsS "http://127.0.0.1:${port}/slots" >"${out_dir}/slots-before.json"

python3 "${harness}" \
  --base-url "http://127.0.0.1:${port}" \
  --model "qwen38-q4km-q4mtp-tp2-mtp${depth}-concurrency" \
  --api-mode native --suite "${suite}" --concurrency "${concurrency_points}" \
  --repeats 1 --max-tokens 128 --seed 42 --timeout 900 --return-token-ids \
  --oracle-digests "${oracle}" \
  --request-id-prefix "qwen38-q4mtp-tp2-mtp${depth}-${attempt}" \
  --request-extra-json '{"cache_prompt":false,"ignore_eos":true,"temperature":0}' \
  --out "${out_dir}/performance.json" | tee "${out_dir}/performance.stdout"

python3 - "${out_dir}/performance.json" >"${out_dir}/qualification.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
rows = d["oracle"]["rows"] + [row for batch in d["batches"] for row in batch["rows"]]
counts_exact = all(row.get("completion_tokens") == 128 for row in rows)
cache_zero = d["oracle"]["cached_tokens_all_zero"] and all(batch["cached_tokens_all_zero"] for batch in d["batches"])
token_ids_complete = all(batch.get("complete_token_id_identity_all") for batch in d["batches"])
cross_base = sum(batch.get("cross_base_oracle_collision_count", 0) for batch in d["batches"])
classification = d.get("classification")
qualified = counts_exact and cache_zero and token_ids_complete and cross_base == 0 and classification in {
    "output-identity-qualified", "output-isolation-qualified-shape-variant"
}
out = {
    "qualified": qualified,
    "classification": classification if qualified else "measured-output-variant",
    "completion_tokens_128_all": counts_exact,
    "cached_tokens_all_zero": cache_zero,
    "complete_token_id_identity_all": token_ids_complete,
    "cross_base_oracle_collision_count": cross_base,
    "request_count": len(rows),
    "points": [{
        "concurrency": batch["concurrency"],
        "aggregate_tok_s": batch["aggregate_tok_s_wall"],
        "per_user_tok_s": batch["aggregate_tok_s_wall"] / batch["concurrency"],
        "oracle_exact": f"{batch['oracle_exact_count']}/{batch['oracle_exact_total']}"
    } for batch in d["batches"]],
}
json.dump(out, sys.stdout, indent=2)
print()
if not qualified:
    raise SystemExit(3)
PY

python3 "${canary}" \
  --base-url "http://127.0.0.1:${port}" \
  --model "qwen38-q4km-q4mtp-tp2-mtp${depth}-concurrency" \
  --concurrency "${parallel_slots}" --rounds 2 --timeout 900 \
  --request-id-prefix "qwen38-q4mtp-tp2-mtp${depth}-${attempt}-semantic" \
  --output-json "${out_dir}/concurrent-quality-canary.json" \
  >"${out_dir}/concurrent-quality-canary.stdout"

curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-after.txt"
curl -fsS "http://127.0.0.1:${port}/slots" >"${out_dir}/slots-after.json"
printf 'PASS: %s\n' "${out_dir}"
