#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
campaign="${CAMPAIGN_ID:-qwen38-fp8-tp2-http-concurrency-oracle-pilot-20260826-r1}"
prereg="${PREREG_PATH:-${repo_root}/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-concurrency-oracle-pilot-r1-prereg.json}"
model_dir="${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-fp8}"
cache_dir="${VLLM_CACHE_DIR:-/mnt/fast-ai/vllm-cache/q38-official-fp8-f01e/vllm-concurrency-p4}"
out_parent="${OUT_DIR:-/mnt/fast-ai/bench-results}"
suite="${SUITE_PATH:-${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json}"
oracle_digests="${ORACLE_DIGESTS:-}"
pilot="${PILOT:-1}"
attempt="${ATTEMPT:-1}"
port="${PORT:-18088}"
container="${CONTAINER_NAME:-qwen38-fp8-tp2-concurrency-r1-a${attempt}}"
image='vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f'
harness="${repo_root}/scripts/bench-openai-concurrency-oracle.py"
client="${repo_root}/scripts/bench-openai-realistic-suite.py"
verifier="${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-model-direct.sh"
manifest="${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json"
run_dir="${out_parent}/${campaign}-attempt${attempt}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'
[[ "${pilot}" == 0 || "${pilot}" == 1 ]] || fail 'PILOT must be 0 or 1'
[[ -d "${model_dir}" && -f "${prereg}" && -f "${suite}" && -f "${harness}" && -f "${client}" ]] || fail 'frozen input missing'
[[ -z "${oracle_digests}" || -f "${oracle_digests}" ]] || fail 'ORACLE_DIGESTS does not exist'
(( pilot == 1 )) || [[ -n "${oracle_digests}" ]] || fail 'publication attempts require ORACLE_DIGESTS'
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"

exec 7>/run/lock/muse-glimmer-gpu-exclusive.lock
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>/tmp/b70-gpu0.lock
flock -n 9 || fail 'GPU 0 lock is held'
exec 10>/tmp/b70-gpu1.lock
flock -n 10 || fail 'GPU 1 lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'
docker ps -a --format '{{.Names}}' | grep -Fxq "${container}" && fail "container already exists: ${container}"

git -C "${repo_root}" fetch origin main --quiet
[[ "$(git -C "${repo_root}" rev-parse HEAD)" == "$(git -C "${repo_root}" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "${repo_root}" status --porcelain)" ]] || fail 'repository must be clean'
docker image inspect "${image}" >/dev/null 2>&1 || fail 'exact pinned image is not local'
[[ "$(findmnt -no FSTYPE --target "${out_parent}")" == ext4 ]] || fail 'output parent must be ext4'

mkdir -p "${run_dir}" "${cache_dir}"
server_log="${run_dir}/server.log"
cleanup_status=not-run
cleanup() {
  set +e
  if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
    docker logs "${container}" >"${server_log}" 2>&1
    docker stop -t 20 "${container}" >/dev/null 2>&1
  fi
  for _ in $(seq 1 60); do
    docker ps -a --format '{{.Names}}' | grep -Fxq "${container}" || break
    sleep 1
  done
  if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
    cleanup_status="container-survived"
  elif pgrep -af 'vllm|qwen38-fp8' | grep -vE "$$|pgrep|grep" >/dev/null; then
    cleanup_status="process-survived"
  elif ss -ltn 2>/dev/null | grep -q ":${port} "; then
    cleanup_status="port-open"
  else
    cleanup_status=clean
  fi
  printf '%s\n' "${cleanup_status}" >"${run_dir}/cleanup-status.txt"
  free -b >"${run_dir}/memory-after.txt"
}
trap cleanup EXIT INT TERM

free -b >"${run_dir}/memory-before.txt"
docker image inspect "${image}" >"${run_dir}/image-inspect.json"
inputs=("${suite}" "${harness}" "${client}" "${verifier}" "${manifest}" "${prereg}" "${BASH_SOURCE[0]}")
[[ -z "${oracle_digests}" ]] || inputs+=("${oracle_digests}")
sha256sum "${inputs[@]}" >"${run_dir}/input-sha256sums.txt"
"${verifier}" "${model_dir}" >"${run_dir}/model-verification.txt"

cmd=(docker run -d --rm --name "${container}"
  --memory 9g --memory-swap 12g
  --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE
  --security-opt label=disable --ipc=host --shm-size=8g
  -p "127.0.0.1:${port}:8000"
  -v "${model_dir}:/model:ro" -v "${cache_dir}:/root/.cache/vllm"
  -e "ZE_AFFINITY_MASK=0,1" -e "ONEAPI_DEVICE_SELECTOR=level_zero:0,1"
  -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn
  -e VLLM_XPU_ENABLE_XPU_GRAPH=1 -e PYTORCH_ALLOC_CONF=expandable_segments:True
  -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo
  -e CCL_ZE_IPC_EXCHANGE=pidfd -e CCL_SEND=direct -e CCL_RECV=direct
  -e CCL_TOPO_P2P_ACCESS=0
  -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296
  -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296
  -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296
  --entrypoint bash "${image}" -lc
  'exec vllm serve /model --served-model-name qwen38-fp8-concurrency --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization fp8 --kv-cache-dtype auto --gpu-memory-utilization 0.80 --max-model-len 4096 --block-size 64 --max-num-seqs 4 --max-num-batched-tokens 256 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only --compilation-config '\''{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'\''')
printf '%q ' "${cmd[@]}" >"${run_dir}/server-command.txt"
printf '\n' >>"${run_dir}/server-command.txt"
"${cmd[@]}" >"${run_dir}/container-id.txt"

healthy=0
for _ in $(seq 1 600); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${run_dir}/health.json" 2>/dev/null; then healthy=1; break; fi
  docker ps --format '{{.Names}}' | grep -Fxq "${container}" || break
  sleep 1
done
docker logs "${container}" >"${server_log}" 2>&1 || true
(( healthy == 1 )) || fail "FP8 TP2 concurrency profile did not become healthy; retained at ${run_dir}"
curl -fsS "http://127.0.0.1:${port}/v1/models" >"${run_dir}/models.json"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${run_dir}/metrics-before.txt" || true

harness_cmd=(python3 "${harness}" --base-url "http://127.0.0.1:${port}"
  --model qwen38-fp8-concurrency --api-mode completions --suite "${suite}"
  --concurrency "1,2,4,8,16,32,64" --repeats 1 --max-tokens 128
  --seed 42 --timeout 1800 --request-extra-json '{"ignore_eos":true,"temperature":0}'
  --return-token-ids --out "${run_dir}/result.json")
[[ -z "${oracle_digests}" ]] || harness_cmd+=(--oracle-digests "${oracle_digests}")
set +e
"${harness_cmd[@]}" | tee "${run_dir}/harness-summary.txt"
harness_status=${PIPESTATUS[0]}
set -e
printf '%s\n' "${harness_status}" >"${run_dir}/harness-exit-status.txt"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${run_dir}/metrics-after.txt" || true
docker logs "${container}" >"${server_log}" 2>&1

python3 -B - "${run_dir}" "${pilot}" >"${run_dir}/qualification.json" <<'PY'
import json, math, pathlib, re, statistics, sys
root = pathlib.Path(sys.argv[1]); pilot = sys.argv[2] == "1"
d = json.loads((root / "result.json").read_text())
oracle = d["oracle"]["rows"]
batches = d["batches"]
rows = oracle + [row for batch in batches for row in batch["rows"]]
oracle_complete = len(oracle) == 64 and all(
    row.get("completion_tokens") == 128
    and len(row.get("token_ids", [])) == 128
    for row in oracle
)
counts_complete = all(row.get("completion_tokens") == 128 for row in rows)
ids_complete = all(len(row.get("token_ids", [])) == 128 for row in rows)
cache_zero = d["oracle"]["cached_tokens_all_zero"] and all(
    batch["cached_tokens_all_zero"] for batch in batches
)
oracle_cache_zero = d["oracle"]["cached_tokens_all_zero"]
collisions = sum(batch.get("cross_base_oracle_collision_count", 0) for batch in batches)
isolation = all(batch.get("complete_token_id_identity_all") for batch in batches) and collisions == 0
def pct(values, p):
    values = sorted(float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(v))
    if not values: return None
    pos = (len(values) - 1) * p
    lo = int(pos); hi = min(lo + 1, len(values) - 1); frac = pos - lo
    return values[lo] * (1 - frac) + values[hi] * frac
def ms(values, p):
    value = pct(values, p)
    return value * 1000 if value is not None else None
latency = []
for batch in batches:
    ttft = [row.get("ttft_s") for row in batch["rows"]]
    elapsed = [row.get("elapsed_s") for row in batch["rows"]]
    latency.append({
        "concurrent_users": batch["concurrency"],
        "aggregate_tok_s_wall": batch["aggregate_tok_s_wall"],
        "ttft_ms_p50": ms(ttft, .50),
        "ttft_ms_p95": ms(ttft, .95),
        "end_to_end_ms_p50": ms(elapsed, .50),
        "end_to_end_ms_p95": ms(elapsed, .95),
        "queued_profile": batch["concurrency"] > 4,
    })
passed = oracle_complete and oracle_cache_zero and (
    pilot or (counts_complete and ids_complete and cache_zero and isolation)
)
out = {
    "classification": (
        "qualified-oracle-pilot" if passed and pilot else
        "output-isolation-qualified-shape-variant" if passed else "failed-closed"
    ),
    "pilot": pilot,
    "oracle_rows_64_complete": oracle_complete,
    "completion_tokens_128_all": counts_complete,
    "complete_token_id_identity_all": ids_complete,
    "cached_tokens_all_zero": cache_zero,
    "cross_base_oracle_collision_count": collisions,
    "server_active_slots": 4,
    "queued_latency_boundary": "concurrency > 4 includes service queueing",
    "latency": latency,
}
json.dump(out, sys.stdout, indent=2, sort_keys=True); print()
if not passed: raise SystemExit(3)
if pilot:
    compact = {
        "schema": "neural.download.concurrency-token-oracle-digests.v1",
        "cached_tokens_zero": d["oracle"]["cached_tokens_all_zero"],
        "rows": [{
            "base_prompt_id": re.sub(r"-c[0-9]+$", "", row["prompt_id"]),
            "prompt_id": row["prompt_id"],
            "prompt_sha256": row["prompt_sha256"],
            "completion_tokens": row["completion_tokens"],
            "token_ids_sha256": __import__("hashlib").sha256(
                json.dumps(row["token_ids"], separators=(",", ":")).encode()
            ).hexdigest(),
        } for row in oracle],
    }
    (root / "oracle-digests.json").write_text(json.dumps(compact, indent=2, sort_keys=True) + "\n")
PY

sha256sum "${run_dir}/result.json" "${run_dir}/qualification.json" >"${run_dir}/result-sha256sums.txt"
[[ -f "${run_dir}/oracle-digests.json" ]] && sha256sum "${run_dir}/oracle-digests.json" >>"${run_dir}/result-sha256sums.txt"
printf 'PASS: %s\n' "${run_dir}"
