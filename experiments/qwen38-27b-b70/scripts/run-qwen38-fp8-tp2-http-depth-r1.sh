#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
campaign=qwen38-fp8-tp2-http-depth-20260826-r1
prereg="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-depth-r1-prereg.json"
model_dir="${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-fp8}"
cache_dir="${VLLM_CACHE_DIR:-/mnt/fast-ai/vllm-cache/q38-official-fp8-f01e/vllm-depth-33024}"
out_parent="${OUT_DIR:-/mnt/fast-ai/bench-results}"
attempt="${ATTEMPT:-1}"
port="${PORT:-18088}"
container="${CONTAINER_NAME:-qwen38-fp8-tp2-depth-r1}"
image='vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f'
fixture="${repo_root}/data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json"
client="${repo_root}/scripts/bench-openai-token-depth-suite.py"
verifier="${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-model-direct.sh"
model_manifest="${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json"
run_dir="${out_parent}/${campaign}-attempt${attempt}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'
[[ -d "${model_dir}" && -f "${prereg}" && -f "${fixture}" && -f "${client}" ]] || fail 'frozen input missing'
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
sha256sum "${fixture}" "${client}" "${verifier}" "${model_manifest}" "${prereg}" >"${run_dir}/input-sha256sums.txt"
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
  'exec vllm serve /model --served-model-name qwen38-fp8-depth --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization fp8 --kv-cache-dtype auto --gpu-memory-utilization 0.80 --max-model-len 33024 --block-size 64 --max-num-seqs 1 --max-num-batched-tokens 4096 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only --compilation-config '\''{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'\''')
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
(( healthy == 1 )) || fail "33,024-token FP8 TP2 profile did not become healthy; retained at ${run_dir}"
curl -fsS "http://127.0.0.1:${port}/v1/models" >"${run_dir}/models.json"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${run_dir}/metrics-before.txt" || true

for depth in 2048 4096 8192 16384 24576 32768; do
  python3 "${client}" --execute --fixture "${fixture}" --depth "${depth}" \
    --context-capacity 33024 --base-url "http://127.0.0.1:${port}" \
    --model qwen38-fp8-depth --response-adapter vllm --timeout 1800 \
    --out "${run_dir}/depth-${depth}.json" >"${run_dir}/depth-${depth}.stdout.json"
done
curl -fsS "http://127.0.0.1:${port}/metrics" >"${run_dir}/metrics-after.txt" || true
docker logs "${container}" >"${server_log}" 2>&1

python3 -B - "${run_dir}" >"${run_dir}/summary.json" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
depths = [2048, 4096, 8192, 16384, 24576, 32768]
rows = [json.loads((root / f"depth-{depth}.json").read_text()) for depth in depths]
points = []
for row in rows:
    depth = row["run_identity"]["active_context_tokens"]
    ttft_s = row["metric_window"]["time_to_first_token_s"]
    points.append({
        "active_context_tokens": depth,
        "status": row["status"],
        "decode_tok_s": row["metric_window"]["conventional_99_interval_tok_s"],
        "ttft_ms": ttft_s * 1000,
        "effective_prompt_throughput_proxy_tok_s": depth / ttft_s,
        "effective_prompt_throughput_proxy_formula": "active_context_tokens / measured_ttft_seconds",
        "cached_tokens_zero": row["gate"]["checks"]["cached_tokens_zero"],
        "output_token_ids_sha256": row["response"]["output_token_ids_sha256"],
    })
passed = len(points) == 6 and [p["active_context_tokens"] for p in points] == depths and all(
    p["status"] == "passed" and p["cached_tokens_zero"] and p["decode_tok_s"] > 0
    for p in points
)
out = {
    "schema": "neural.download.qwen38-fp8-vllm-http-depth-result.v1",
    "campaign_id": "qwen38-fp8-tp2-http-depth-20260826-r1",
    "classification": "qualified-exact-depth" if passed else "failed-closed",
    "tuple": "Qwen3.8-27B official FP8 TP2; FP16 KV; target-only/MTP0; PIECEWISE size-one graph; 33,024-token capacity; one service slot",
    "points": points,
    "workload_boundary": "Grade-C exact repeated-token context fixture; every point measured; no interpolation or extrapolation; not natural prose.",
    "proxy_boundary": "Effective prompt throughput is exact prompt tokens divided by observed HTTP TTFT. It includes scheduling, chunked prefill, and first-token work; it is not a server-only kernel prefill rate.",
}
json.dump(out, sys.stdout, indent=2, sort_keys=True); print()
if not passed: raise SystemExit(3)
PY

sha256sum "${run_dir}"/depth-*.json "${run_dir}/summary.json" >"${run_dir}/result-sha256sums.txt"
printf 'PASS: %s\n' "${run_dir}"
