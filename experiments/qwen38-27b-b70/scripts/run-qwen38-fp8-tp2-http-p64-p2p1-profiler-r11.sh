#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
campaign="${CAMPAIGN_ID:-qwen38-fp8-tp2-http-p64-p2p1-profiler-20260826-r11}"
prereg="${PREREG_PATH:-${repo_root}/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-profiler-r11-prereg.json}"
model_dir="${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-fp8}"
cache_dir="${VLLM_CACHE_DIR:-/mnt/fast-ai/vllm-cache/q38-official-fp8-f01e/vllm-p64-p2p1-profiler-r11}"
out_parent="${OUT_DIR:-/mnt/fast-ai/bench-results}"
suite="${SUITE_PATH:-${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json}"
oracle_digests="${ORACLE_DIGESTS:-${repo_root}/experiments/qwen38-27b-b70/data/qwen38-fp8-tp2-http-concurrency-oracle-pilot-20260826-r1-attempt1/oracle-digests.json}"
port="${PORT:-18089}"
container="${CONTAINER_NAME:-qwen38-fp8-tp2-p64-p2p1-profiler-r11}"
image='vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f'
harness="${repo_root}/scripts/bench-openai-concurrency-oracle.py"
qualifier="${repo_root}/scripts/qualify-openai-concurrency-attempt.py"
verifier="${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-model-direct.sh"
manifest="${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json"
run_dir="${out_parent}/${campaign}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'
[[ -d "${model_dir}" && -f "${prereg}" && -f "${suite}" ]] || fail 'frozen input missing'
[[ -f "${oracle_digests}" && -f "${harness}" && -f "${qualifier}" ]] || fail 'frozen harness input missing'
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

mkdir -p "${run_dir}/profiles" "${cache_dir}"
server_log="${run_dir}/server.log"
cleanup_status=not-run
cleanup() {
  set +e
  if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
    docker logs "${container}" >"${server_log}" 2>&1
    docker stop -t 30 "${container}" >/dev/null 2>&1
  fi
  for _ in $(seq 1 60); do
    docker ps -a --format '{{.Names}}' | grep -Fxq "${container}" || break
    sleep 1
  done
  if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
    cleanup_status="container-survived"
  elif ps -eo comm=,args= | awk '
    $1 !~ /^(bash|dash|sh|timeout|awk|ps|grep|pgrep)$/ &&
    $0 ~ /(vllm|qwen38-fp8)/ { found=1 }
    END { exit !found }
  '; then
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
sha256sum "${suite}" "${oracle_digests}" "${harness}" "${qualifier}" \
  "${verifier}" "${manifest}" "${prereg}" "${BASH_SOURCE[0]}" \
  >"${run_dir}/input-sha256sums.txt"
"${verifier}" "${model_dir}" >"${run_dir}/model-verification.txt"

profiler_config='{"profiler":"torch","torch_profiler_dir":"/profiles","torch_profiler_with_stack":false,"torch_profiler_record_shapes":false,"torch_profiler_with_memory":false,"torch_profiler_with_flops":false,"torch_profiler_use_gzip":true,"ignore_frontend":true,"delay_iterations":10,"max_iterations":8}'
# REPRO_ACTIVE_SLOTS is intentionally expanded by bash inside the container.
# shellcheck disable=SC2016
cmd=(docker run -d --rm --name "${container}"
  --memory 9g --memory-swap 12g
  --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE
  --security-opt label=disable --ipc=host --shm-size=8g
  -p "127.0.0.1:${port}:8000"
  -v "${model_dir}:/model:ro" -v "${cache_dir}:/root/.cache/vllm"
  -v "${run_dir}/profiles:/profiles"
  -e 'ZE_AFFINITY_MASK=0,1' -e 'ONEAPI_DEVICE_SELECTOR=level_zero:0,1'
  -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn
  -e VLLM_XPU_ENABLE_XPU_GRAPH=1 -e PYTORCH_ALLOC_CONF=expandable_segments:True
  -e VLLM_RPC_TIMEOUT=1800000
  -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo
  -e CCL_ZE_IPC_EXCHANGE=pidfd -e CCL_SEND=direct -e CCL_RECV=direct
  -e CCL_TOPO_P2P_ACCESS=1
  -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296
  -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296
  -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296
  -e REPRO_ACTIVE_SLOTS=64
  -e "PROFILER_CONFIG=${profiler_config}"
  --entrypoint bash "${image}" -lc
  'exec vllm serve /model --served-model-name qwen38-fp8-concurrency --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization fp8 --kv-cache-dtype auto --gpu-memory-utilization 0.80 --max-model-len 4096 --block-size 64 --max-num-seqs "${REPRO_ACTIVE_SLOTS}" --max-num-batched-tokens 256 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only --compilation-config '\''{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'\'' --profiler-config "${PROFILER_CONFIG}"')

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
(( healthy == 1 )) || fail "profile server did not become healthy; retained at ${run_dir}"
curl -fsS "http://127.0.0.1:${port}/v1/models" >"${run_dir}/models.json"

curl -fsS -X POST "http://127.0.0.1:${port}/start_profile" >"${run_dir}/profile-start.json"
set +e
python3 "${harness}" --base-url "http://127.0.0.1:${port}" \
  --model qwen38-fp8-concurrency --api-mode completions --suite "${suite}" \
  --concurrency 64 --repeats 1 --max-tokens 128 --seed 42 --timeout 1800 \
  --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids \
  --oracle-digests "${oracle_digests}" --out "${run_dir}/result.json" \
  | tee "${run_dir}/harness-summary.txt"
harness_status=${PIPESTATUS[0]}
set -e
printf '%s\n' "${harness_status}" >"${run_dir}/harness-exit-status.txt"
curl -fsS -X POST "http://127.0.0.1:${port}/stop_profile" >"${run_dir}/profile-stop.json" || true

for _ in $(seq 1 180); do
  find "${run_dir}/profiles" -type f -size +0c -print -quit | grep -q . && break
  sleep 1
done
find "${run_dir}/profiles" -type f -size +0c -printf '%P %s bytes\n' | sort >"${run_dir}/profile-files.txt"
[[ -s "${run_dir}/profile-files.txt" ]] || fail 'profiler produced no non-empty artifact'
docker logs "${container}" >"${server_log}" 2>&1
[[ "$(grep -c 'CCL_TOPO_P2P_ACCESS changed to be 1' "${server_log}")" -eq 2 ]] \
  || fail 'server log does not prove P2P activation on both ranks'

python3 "${qualifier}" --result "${run_dir}/result.json" \
  --out "${run_dir}/qualification.json" --active-slots 64 --pilot \
  --pilot-require-batch-gates --expected-oracle-rows 64
sha256sum "${run_dir}/result.json" "${run_dir}/qualification.json" \
  "${run_dir}/profile-files.txt" >"${run_dir}/result-sha256sums.txt"
printf 'PASS: %s\n' "${run_dir}"
