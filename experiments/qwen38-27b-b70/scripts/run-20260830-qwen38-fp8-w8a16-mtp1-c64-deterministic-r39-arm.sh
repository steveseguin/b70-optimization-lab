#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
arm=${ARM:?set ARM to control or candidate}
attempt=${ATTEMPT:?set ATTEMPT to A or B}
pilot=${PILOT:-0}
oracle=${ORACLE_DIGESTS:-}
campaign=qwen38-fp8-w8a16-mtp1-c64-deterministic-20260830-r39
out_parent=${OUT_DIR:-/mnt/fast-ai/bench-results}
run_dir=${out_parent}/${campaign}-${arm}-${attempt}
cache_dir=${CACHE_DIR:-/mnt/fast-ai/vllm-cache/${campaign}-${arm}-${attempt}}
model_dir=${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-fp8}
port=${PORT:-18159}
container=${CONTAINER_NAME:-qwen38-fp8-r39-${arm}-${attempt}}
served_model=qwen38-fp8-r39
suite=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
prereg=${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-fp8-w8a16-mtp1-c64-deterministic-r39-prereg.json
harness=${repo}/scripts/bench-openai-concurrency-oracle.py
pilot_harness=${repo}/scripts/bench-openai-concurrency-batch-oracle-pilot.py
qualifier=${repo}/scripts/qualify-openai-concurrency-attempt.py
verifier=${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-model-direct.sh
control_launcher=${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-server.sh
candidate_launcher=${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-strict-server.sh
control_image=neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-r15
control_image_id=sha256:d19f802ba702a9cb94b155f807a4674a0100702aee838323372f740d7168e34e
candidate_image=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31
candidate_image_id=sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "${arm}" == control || "${arm}" == candidate ]] || fail 'ARM must be control or candidate'
[[ "${attempt}" == A || "${attempt}" == B ]] || fail 'ATTEMPT must be A or B'
[[ "${pilot}" == 0 || "${pilot}" == 1 ]] || fail 'PILOT must be 0 or 1'
[[ "${pilot}" == 0 || ( "${arm}" == control && "${attempt}" == A ) ]] || fail 'only control A may generate the oracle'
[[ "${pilot}" == 1 || -f "${oracle}" ]] || fail 'validation arms require ORACLE_DIGESTS'
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
[[ ! -e "${cache_dir}" ]] || fail "fresh compile cache already exists: ${cache_dir}"
[[ -d "${model_dir}" ]] || fail "model directory missing: ${model_dir}"
for input in "${suite}" "${prereg}" "${harness}" "${pilot_harness}" \
  "${qualifier}" "${verifier}" "${control_launcher}" "${candidate_launcher}"; do
  [[ -f "${input}" ]] || fail "frozen input missing: ${input}"
done
[[ "$(findmnt -no FSTYPE --target "${out_parent}")" == ext4 ]] || fail 'output parent must be ext4'
[[ "$(findmnt -no FSTYPE --target "${model_dir}")" == ext4 ]] || fail 'model must be on local ext4 storage'

exec 7>/run/lock/muse-glimmer-gpu-exclusive.lock
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>/tmp/b70-gpu0.lock
flock -n 9 || fail 'GPU 0 lock is held'
exec 10>/tmp/b70-gpu1.lock
flock -n 10 || fail 'GPU 1 lock is held'
pgrep -af 'llama-server|vllm serve|vllm.entrypoints|api_server' >/dev/null && fail 'another model service is running'
docker ps -a --format '{{.Names}}' | grep -Fxq "${container}" && fail "container already exists: ${container}"

git -C "${repo}" fetch origin main --quiet
[[ "$(git -C "${repo}" rev-parse HEAD)" == "$(git -C "${repo}" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "${repo}" status --porcelain)" ]] || fail 'repository must be clean'

if [[ "${arm}" == control ]]; then
  image=${control_image}; expected_image_id=${control_image_id}; launcher=${control_launcher}
else
  image=${candidate_image}; expected_image_id=${candidate_image_id}; launcher=${candidate_launcher}
fi
actual_image_id=$(docker image inspect "${image}" --format '{{.Id}}' 2>/dev/null) || fail "image missing: ${image}"
[[ "${actual_image_id}" == "${expected_image_id}" ]] || fail "image identity mismatch: ${image}"

mkdir -p "${run_dir}"
date -u +%Y-%m-%dT%H:%M:%SZ >"${run_dir}/start-utc.txt"
free -b >"${run_dir}/memory-before.txt"
docker image inspect "${image}" >"${run_dir}/image-inspect.json"
inputs=("${suite}" "${prereg}" "${harness}" "${pilot_harness}" "${qualifier}" \
  "${verifier}" "${control_launcher}" "${candidate_launcher}" "${BASH_SOURCE[0]}")
[[ "${pilot}" == 1 ]] || inputs+=("${oracle}")
sha256sum "${inputs[@]}" >"${run_dir}/input-sha256sums.txt"

server_pid=
cleanup_status=not-run
cleanup() {
  set +e
  if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
    docker inspect "${container}" >"${run_dir}/container-inspect-final.json" 2>/dev/null || true
    docker logs "${container}" >"${run_dir}/docker.log" 2>&1 || true
    docker stop -t 30 "${container}" >/dev/null 2>&1 || true
  fi
  [[ -z "${server_pid}" ]] || wait "${server_pid}" 2>/dev/null || true
  for _ in $(seq 1 60); do
    docker ps -a --format '{{.Names}}' | grep -Fxq "${container}" || break
    sleep 1
  done
  if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
    cleanup_status='container-survived'
  elif pgrep -af 'vllm serve|vllm.entrypoints|api_server' >/dev/null; then
    cleanup_status='process-survived'
  elif ss -ltn 2>/dev/null | grep -q ":${port} "; then
    cleanup_status='port-open'
  else
    cleanup_status=clean
  fi
  printf '%s\n' "${cleanup_status}" >"${run_dir}/cleanup-status.txt"
  free -b >"${run_dir}/memory-after.txt" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

common_env=(
  IMAGE="${image}"
  MODEL_DIR="${model_dir}"
  VLLM_CACHE_DIR="${cache_dir}"
  CONTAINER_NAME="${container}"
  PORT="${port}"
  MAX_MODEL_LEN=256
  MAX_NUM_SEQS=128
  MAX_NUM_BATCHED_TOKENS=512
  GPU_MEMORY_UTILIZATION=0.96
  SERVED_MODEL_NAME="${served_model}"
  VLLM_XPU_ENABLE_XPU_GRAPH=0
  VLLM_XPU_FP8_BLOCK_W8A16=1
  VLLM_BATCH_INVARIANT=0
  VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0
  VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1
  VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0
  VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
  VLLM_XPU_GDN_NATIVE_FALLBACK=1
  TORCHINDUCTOR_DETERMINISTIC=1
  CCL_P2P_ACCESS=1
)
if [[ "${arm}" == candidate ]]; then
  common_env+=(EXPECTED_IMAGE_ID="${candidate_image_id}")
fi
printf '%q ' env "${common_env[@]}" "${launcher}" >"${run_dir}/server-command.txt"
printf '\n' >>"${run_dir}/server-command.txt"
env "${common_env[@]}" "${launcher}" >"${run_dir}/server.log" 2>&1 &
server_pid=$!

healthy=0
for _ in $(seq 1 900); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${run_dir}/health.json" 2>/dev/null; then healthy=1; break; fi
  kill -0 "${server_pid}" 2>/dev/null || break
  sleep 1
done
(( healthy == 1 )) || fail "server did not become healthy; see ${run_dir}/server.log"
docker inspect "${container}" >"${run_dir}/container-inspect.json"
curl -fsS "http://127.0.0.1:${port}/v1/models" >"${run_dir}/models.json"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${run_dir}/metrics-before.txt" || true

request_extra='{"ignore_eos":true,"temperature":0,"top_p":1}'
if [[ "${pilot}" == 1 ]]; then
  python3 "${pilot_harness}" \
    --base-url "http://127.0.0.1:${port}" --model "${served_model}" \
    --api-mode completions --suite "${suite}" --concurrency 64 --max-tokens 128 \
    --seed 42 --timeout 1800 --return-token-ids \
    --request-id-prefix "qwen38-fp8-r39-${arm}-${attempt}" \
    --request-extra-json "${request_extra}" --out "${run_dir}/result.json" \
    | tee "${run_dir}/harness-summary.txt"
  python3 "${qualifier}" --result "${run_dir}/result.json" \
    --out "${run_dir}/qualification.json" --active-slots 128 \
    --expected-oracle-rows 64 --pilot --pilot-require-batch-gates \
    --pilot-from-batch --oracle-out "${run_dir}/oracle-digests.json"
else
  python3 "${harness}" \
    --base-url "http://127.0.0.1:${port}" --model "${served_model}" \
    --api-mode completions --suite "${suite}" --concurrency 64 --repeats 1 \
    --max-tokens 128 --seed 42 --timeout 1800 --return-token-ids \
    --request-id-prefix "qwen38-fp8-r39-${arm}-${attempt}" \
    --request-extra-json "${request_extra}" --oracle-digests "${oracle}" \
    --out "${run_dir}/result.json" | tee "${run_dir}/harness-summary.txt"
  python3 "${qualifier}" --result "${run_dir}/result.json" \
    --out "${run_dir}/qualification.json" --active-slots 128 \
    --expected-oracle-rows 64
fi

curl -fsS "http://127.0.0.1:${port}/health" >"${run_dir}/post-health.json"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${run_dir}/metrics-after.txt" || true
docker logs "${container}" >"${run_dir}/docker.log" 2>&1 || true
start=$(cat "${run_dir}/start-utc.txt")
journalctl -k -b --since "${start}" --no-pager | \
  grep -Ei 'xe.*(fault|reset|hang)|device lost|CAT fault|oom|out of memory' \
  >"${run_dir}/kernel-errors.txt" || true
[[ ! -s "${run_dir}/kernel-errors.txt" ]] || fail 'kernel/GPU/OOM error evidence found'

python3 - "${run_dir}" "${arm}" "${attempt}" "${pilot}" "${image}" "${expected_image_id}" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
arm, attempt, pilot = sys.argv[2], sys.argv[3], sys.argv[4] == "1"
result = json.loads((root / "result.json").read_text())
quality = json.loads((root / "qualification.json").read_text())
batch = result["batches"][0]
passed = (
    quality["batch_gates_passed"] is True
    and quality["cached_tokens_all_zero"] is True
    and quality["completion_tokens_128_all"] is True
    and quality["complete_token_id_identity_all"] is True
    and quality["cross_base_oracle_collision_count"] == 0
    and (pilot or batch["oracle_exact_all"] is True)
)
summary = {
    "schema": "neural.download.qwen38-fp8-w8a16-mtp1-c64-r39-arm.v1",
    "arm": arm,
    "attempt": attempt,
    "oracle_generation_pilot": pilot,
    "publishable_attempt": not pilot and passed,
    "quality_passed": passed,
    "aggregate_tok_s_c64": batch["aggregate_tok_s_wall"],
    "request_count": batch["request_count"],
    "total_completion_tokens": batch["total_completion_tokens"],
    "oracle_exact_count": batch["oracle_exact_count"],
    "oracle_exact_total": batch["oracle_exact_total"],
    "cached_tokens_all_zero": quality["cached_tokens_all_zero"],
    "complete_token_id_identity_all": quality["complete_token_id_identity_all"],
    "cross_base_oracle_collision_count": quality["cross_base_oracle_collision_count"],
    "image": sys.argv[5],
    "image_id": sys.argv[6],
    "scope": "directly measured TP2 c64 p128 official FP8/W8A16; no extrapolation",
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
if not passed:
    raise SystemExit(3)
PY

sha256sum "${run_dir}/result.json" "${run_dir}/qualification.json" \
  "${run_dir}/summary.json" >"${run_dir}/result-sha256sums.txt"
trap - EXIT INT TERM
cleanup
[[ "${cleanup_status}" == clean ]] || fail "cleanup failed: ${cleanup_status}"
printf 'PASS: %s\n' "${run_dir}"
