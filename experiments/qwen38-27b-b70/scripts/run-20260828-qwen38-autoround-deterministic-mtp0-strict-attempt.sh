#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
mode=${EXECUTION_MODE:?set EXECUTION_MODE to eager or compiled}
attempt=${ATTEMPT:?set ATTEMPT to a unique label}
out=${OUT_DIR:?set OUT_DIR to a new evidence directory}
cache=${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a new cache directory}
port=${PORT:?set PORT to a unique port}
expected_image_id=${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID}
expected_xpu_extension_sha256=${EXPECTED_XPU_EXTENSION_SHA256:?set EXPECTED_XPU_EXTENSION_SHA256}
expected_gdn_library_sha256=${EXPECTED_GDN_LIBRARY_SHA256:?set EXPECTED_GDN_LIBRARY_SHA256}
expected_xpu_communicator_sha256=${EXPECTED_XPU_COMMUNICATOR_SHA256:-5ab2ea5d9e049e6b53e2d56d1e3419ce01d1988e8be5295bab1f912a7fdbf74d}
model=${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-devan}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1}
gpu_ids=${GPU_IDS:-2,3}
tensor_parallel_size=${TENSOR_PARALLEL_SIZE:-2}
min_host_memory_gib=${MIN_HOST_MEMORY_GIB:-80}
container_memory=${CONTAINER_MEMORY:-96g}
container_memory_swap=${CONTAINER_MEMORY_SWAP:-104g}
suite=${SUITE:-$repo/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}
container="q38-ar-det-mtp0-${mode}-${attempt}"
served="qwen38-autoround-deterministic-mtp0"
journal_start=$(date +%s)
server_pid=""

[[ "$mode" == eager || "$mode" == compiled ]] || { printf 'invalid mode\n' >&2; exit 2; }
if [[ -v GDN_NATIVE_FALLBACK || -v GDN_SYNC_AFTER_NATIVE ]]; then
  printf 'GDN fallback/sync environment treatments are unsupported by this pinned image\n' >&2
  exit 2
fi
[[ ! -e "$out" && ! -e "$cache" ]] || { printf 'output and cache paths must be new\n' >&2; exit 1; }
mkdir -p "$out"

cleanup() {
  local rc=$?
  set +e
  docker stop -t 30 "$container" >/dev/null 2>&1 || true
  [[ -z "$server_pid" ]] || wait "$server_pid" 2>/dev/null || true
  journalctl -k --since "@${journal_start}" --no-pager >"$out/kernel-journal.log" 2>"$out/kernel-journal.err"
  printf '%s\n' "$rc" >"$out/attempt.rc"
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

"$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
  "$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json" "$model" \
  --json "$out/model-verify.json" >"$out/model-verify.log"

python3 - "$out/campaign-identity.json" "$mode" "$attempt" "$model" "$cache" "$suite" "$port" "$container" "$image" "$expected_image_id" "$expected_xpu_extension_sha256" "$expected_gdn_library_sha256" "$expected_xpu_communicator_sha256" "$gpu_ids" "$tensor_parallel_size" "$min_host_memory_gib" "$container_memory" "$container_memory_swap" <<'PY'
import datetime as dt, hashlib, json, pathlib, sys
path, mode, attempt, model, cache, suite, port, container, image, image_id, xpu_sha, gdn_sha, communicator_sha, gpu_ids, tp_size, min_mem, container_mem, container_swap = sys.argv[1:]
s = pathlib.Path(suite)
value = {
  "schema": "neural.download.qwen38-autoround-deterministic-mtp0-strict-attempt.v1",
  "created_utc": dt.datetime.now(dt.UTC).isoformat(), "mode": mode,
  "attempt": attempt, "model_dir": model, "fresh_compile_cache": cache,
  "suite": str(s), "suite_sha256": hashlib.sha256(s.read_bytes()).hexdigest(),
  "port": int(port), "container": container, "image": image,
  "image_id": image_id, "xpu_extension_sha256": xpu_sha,
  "gdn_library_sha256": gdn_sha, "xpu_communicator_sha256": communicator_sha,
  "tensor_parallel": int(tp_size), "physical_gpus": [int(item) for item in gpu_ids.split(",")],
  "host_memory_gate_gib": int(min_mem), "container_memory": container_mem,
  "container_memory_swap": container_swap,
  "gdn_path": "pinned-image-default-native-xpu",
  "mtp_depth": 0, "xpu_graph": False, "inductor_deterministic": True,
  "prefix_cache": False, "prompt_or_response_reuse": False,
  "performance_contract": {"complete_fixed_suite": True, "max_tokens": 512,
    "metric_events": 100, "metric_intervals": 99,
    "aggregation": "median-of-prompt-class-medians", "cached_tokens_required": 0,
    "temperature": 0, "ignore_eos": False}
}
pathlib.Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+"\n")
PY

env EXECUTION_MODE="$mode" IMAGE="$image" EXPECTED_IMAGE_ID="$expected_image_id" \
  EXPECTED_XPU_EXTENSION_SHA256="$expected_xpu_extension_sha256" \
  EXPECTED_GDN_LIBRARY_SHA256="$expected_gdn_library_sha256" \
  EXPECTED_XPU_COMMUNICATOR_SHA256="$expected_xpu_communicator_sha256" \
  MODEL_DIR="$model" VLLM_CACHE_DIR="$cache" CONTAINER_NAME="$container" \
  PORT="$port" SERVED_MODEL_NAME="$served" \
  GPU_IDS="$gpu_ids" MIN_HOST_MEMORY_GIB="$min_host_memory_gib" \
  TENSOR_PARALLEL_SIZE="$tensor_parallel_size" \
  CONTAINER_MEMORY="$container_memory" CONTAINER_MEMORY_SWAP="$container_memory_swap" \
  "$repo/repro/qwen38-27b-autoround-int4-b70/scripts/run-current-deterministic-mtp0-server.sh" \
  >"$out/server.log" 2>&1 &
server_pid=$!

deadline=$((SECONDS + 900))
until curl -fsS "http://127.0.0.1:${port}/health" >"$out/health.json" 2>"$out/health.err"; do
  kill -0 "$server_pid" 2>/dev/null || { tail -120 "$out/server.log" >&2; exit 1; }
  (( SECONDS < deadline )) || { printf 'readiness timeout\n' >&2; exit 1; }
  sleep 3
done
docker inspect "$container" >"$out/container-inspect.json"
curl -fsS "http://127.0.0.1:${port}/v1/models" >"$out/models.json"
grep -Fq 'quantization=inc' "$out/server.log"
grep -Fq 'TORCHINDUCTOR_DETERMINISTIC' "$out/container-inspect.json"
grep -Fq 'VLLM_XPU_FP8_BLOCK_W8A16=0' "$out/container-inspect.json"
grep -Fq 'VLLM_XPU_ENABLE_XPU_GRAPH=0' "$out/container-inspect.json"
if [[ "$mode" == eager ]]; then grep -Fq 'enforce_eager=True' "$out/server.log"; else grep -Fq 'enforce_eager=False' "$out/server.log"; fi
if grep -Fq 'Graph capturing finished' "$out/server.log"; then
  printf 'unexpected XPU Graph capture\n' >&2
  exit 1
fi

python3 "$repo/scripts/bench-openai-realistic-suite.py" \
  --base-url "http://127.0.0.1:${port}" --model "$served" --api-mode completions \
  --suite "$suite" --max-tokens 512 --metric-tokens 100 --seed 42 --timeout 900 \
  --return-token-ids --require-natural-eos \
  --request-extra-json '{"temperature":0,"top_p":1}' --out "$out/performance.json" \
  >"$out/performance.stdout"
python3 "$repo/scripts/neural-download-canaries.py" \
  --base-url "http://127.0.0.1:${port}" --model "$served" --out "$out/canaries.json" \
  >"$out/canaries.stdout"

python3 - "$out/performance.json" "$out/canaries.json" "$out/qualification.json" <<'PY'
import json, pathlib, sys
p=json.load(open(sys.argv[1])); c=json.load(open(sys.argv[2])); g=p["realistic_final_gate"]
assert g["passed"] and p["fresh_response_validity"]["performance_gate_eligible"]
assert g["cached_tokens_all_zero"] and len(p["rows"]) == 12 and c["pass_all"]
metric=p["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
pathlib.Path(sys.argv[3]).write_text(json.dumps({"status":"passed","strict_metric_tok_s":metric,
  "prompt_count":12,"canaries_passed":True,"promotion_authorized":False},indent=2)+"\n")
print(f"class_balanced_median_tok_s={metric:.12f}")
PY

curl -fsS "http://127.0.0.1:${port}/health" >"$out/post-health.json"
docker stop -t 30 "$container" >/dev/null
wait "$server_pid" || true
server_pid=""
if docker inspect "$container" >/dev/null 2>&1; then
  printf 'container remained after bounded shutdown\n' >&2
  exit 1
fi
if ss -ltn | grep -Eq ":${port}[[:space:]]"; then
  printf 'port remained occupied after bounded shutdown\n' >&2
  exit 1
fi
if pgrep -af '[E]ngineCore|[v]llm serve.*qwen3.8-27b-int4-autoround' >/dev/null; then
  printf 'vLLM process remained after bounded shutdown\n' >&2
  exit 1
fi
journalctl -k --since "@${journal_start}" --no-pager >"$out/kernel-journal.log"
if grep -Eqi 'xe .*reset|xe .*fault|xe .*timeout|xe .*timed out|xe .*fatal|xe .*wedged|xe .*failed|device lost|out of memory|oom-kill' "$out/kernel-journal.log"; then
  printf 'new GPU/kernel/OOM fault event detected\n' >&2
  exit 1
fi
printf 'PASS strict mode=%s attempt=%s\n' "$mode" "$attempt"
