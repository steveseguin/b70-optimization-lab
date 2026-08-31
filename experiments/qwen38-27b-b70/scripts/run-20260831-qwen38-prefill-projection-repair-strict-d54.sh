#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
campaign=${CAMPAIGN_ID:-qwen38-prefill-projection-repair-strict-20260831-d54}
root=/mnt/fast-ai/bench-results/$campaign
cache=/mnt/fast-ai/vllm-cache/$campaign
model=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround
image=neural-download/vllm-openai-xpu:qwen38-autoround-gdn-int4-prefill-pad512-r1
image_id=sha256:03da963d9d9b3b2cfc5cb7d9f1bc0aeb9ebd7e1b9495e3cad4e5b9e5dd4fc493
hook=$repo/repro/qwen38-27b-autoround-int4-b70/patches/qwen38-prefill-projection-repair-sitecustomize.py
prereg=${PREREG_PATH:-$repo/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-prefill-projection-repair-strict-d54-prereg.md}
suite=$repo/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json
bench=$repo/scripts/bench-openai-realistic-suite.py
canaries=$repo/scripts/neural-download-canaries.py
served=qwen38-prefill-projection-repair
container=${CONTAINER_NAME:-q38-prefill-projection-repair-d54}
port=${PORT:-18354}
reference_performance=${REFERENCE_PERFORMANCE:-}
projection_synchronize=${VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE:-1}
tensor_parallel_size=${TENSOR_PARALLEL_SIZE:-1}
gpu_mask=${GPU_MASK:-0}
device_selector=${ONEAPI_SELECTOR:-level_zero:0}
container_memory=${CONTAINER_MEMORY:-12g}
max_num_batched_tokens=${MAX_NUM_BATCHED_TOKENS:-2048}
speculative_config_json=${SPECULATIVE_CONFIG_JSON:-}
journal_start=$(date +%s)

fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }
cleanup(){
  local rc=$?
  set +e
  docker logs "$container" >"$root/server-final.log" 2>&1
  docker rm -f "$container" >/dev/null 2>&1
  journalctl -k --since "@${journal_start}" --no-pager >"$root/kernel-journal.log" 2>"$root/kernel-journal.err"
  printf '%s\n' "$rc" >"$root/attempt.rc"
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

[[ -f "$hook" && -f "$prereg" && -f "$suite" && -f "$bench" && -f "$canaries" ]] || fail 'missing frozen input'
[[ -d "$model" && ! -L "$model" && "$(findmnt -n -o FSTYPE -T "$model")" == ext4 ]] || fail 'model must be local ext4'
[[ ! -e "$root" && ! -e "$cache" ]] || fail 'output or cache root already exists'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" && -z "$(docker ps -q)" ]] || fail 'dirty repository or active container'
! pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server' >/dev/null || fail 'another model server is running'
exec 7>/tmp/b70-benchmark.lock; flock -n 7 || fail 'benchmark lock held'
exec 8>/tmp/b70-gpu0.lock; flock -n 8 || fail 'GPU0 lock held'
if [[ "$tensor_parallel_size" == 2 ]]; then
  [[ "$gpu_mask" == 0,1 && "$device_selector" == level_zero:0,1 ]] || fail 'TP2 requires local GPUs 0,1'
  exec 9>/tmp/b70-gpu1.lock; flock -n 9 || fail 'GPU1 lock held'
elif [[ "$tensor_parallel_size" != 1 ]]; then
  fail 'only TP1 and TP2 are supported by this local runner'
fi
mkdir -p "$root" "$cache"
sha256sum "$0" "$hook" "$prereg" "$suite" "$bench" "$canaries" >"$root/input-sha256sums.txt"
if [[ -n "$reference_performance" ]]; then
  [[ -f "$reference_performance" ]] || fail 'reference performance is absent'
  sha256sum "$reference_performance" >>"$root/input-sha256sums.txt"
fi
"$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
  "$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json" "$model" \
  --json "$root/model-verify.json" >"$root/model-verify.log"
server_extra_args=()
if [[ -n "$speculative_config_json" ]]; then
  python3 -c 'import json,sys; json.loads(sys.argv[1])' "$speculative_config_json"
  server_extra_args=(--speculative-config "$speculative_config_json")
fi

docker run -d --name "$container" --ulimit core=0 --memory "$container_memory" --memory-swap 36g \
  --device /dev/dri:/dev/dri --volume /dev/dri/by-path:/dev/dri/by-path:ro \
  --group-add video --group-add render --security-opt label=disable --ipc=host --shm-size=16g \
  --publish "127.0.0.1:${port}:8000" --volume "$model:/model:ro" \
  --volume "$cache:/run-cache" --volume "$hook:/instrument/sitecustomize.py:ro" \
  --env PYTHONPATH=/instrument --env VLLM_XPU_QWEN38_PREFILL_PROJECTION_REPAIR=1 \
  --env "VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE=$projection_synchronize" \
  --env "ZE_AFFINITY_MASK=$gpu_mask" --env "ONEAPI_DEVICE_SELECTOR=$device_selector" \
  --env VLLM_TARGET_DEVICE=xpu --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
  --env VLLM_NO_USAGE_STATS=1 --env PYTHONHASHSEED=0 \
  --env VLLM_XPU_ENABLE_XPU_GRAPH=0 --env VLLM_XPU_GRAPH=0 \
  --env VLLM_XPU_FP8_BLOCK_W8A16=0 --env VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=1 \
  --env VLLM_CACHE_ROOT=/run-cache/vllm --env XDG_CACHE_HOME=/run-cache/xdg \
  --env PYTORCH_ALLOC_CONF=expandable_segments:True --env CCL_ZE_IPC_EXCHANGE=sockets \
  "$image" /model --host 0.0.0.0 --port 8000 --trust-remote-code \
  --served-model-name "$served" --tensor-parallel-size "$tensor_parallel_size" --pipeline-parallel-size 1 \
  --data-parallel-size 1 --dtype float16 --kv-cache-dtype auto \
  --gpu-memory-utilization 0.80 --max-model-len 2048 --block-size 64 \
  --max-num-seqs 1 --max-num-batched-tokens "$max_num_batched_tokens" --no-enable-prefix-caching \
  --enable-prompt-tokens-details --language-model-only --enforce-eager "${server_extra_args[@]}" \
  >"$root/container-id.txt"

deadline=$((SECONDS+900))
until curl -fsS "http://127.0.0.1:${port}/health" >"$root/health.json" 2>"$root/health.err"; do
  [[ "$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || true)" == true ]] || { docker logs "$container" >&2 || true; fail 'server exited'; }
  (( SECONDS < deadline )) || fail 'readiness timeout'
  sleep 3
done
docker inspect "$container" >"$root/container-inspect.json"
docker logs "$container" >"$root/server-startup.log" 2>&1
[[ "$(docker inspect --format '{{.Image}}' "$container")" == "$image_id" ]] || fail 'image receipt mismatch'
if [[ -n "$speculative_config_json" ]]; then
  spec_depth=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["num_speculative_tokens"])' "$speculative_config_json")
  grep -Fq "num_spec_tokens=${spec_depth}" "$root/server-startup.log" || fail 'speculator depth receipt missing'
fi

python3 "$bench" --base-url "http://127.0.0.1:${port}" --model "$served" \
  --api-mode completions --suite "$suite" --max-tokens 512 --metric-tokens 100 \
  --seed 42 --timeout 900 --return-token-ids --require-natural-eos \
  --request-extra-json '{"temperature":0,"top_p":1}' --out "$root/performance.json" \
  >"$root/performance.stdout"
python3 "$canaries" --base-url "http://127.0.0.1:${port}" --model "$served" \
  --out "$root/canaries.json" >"$root/canaries.stdout"
curl -fsS "http://127.0.0.1:${port}/health" >"$root/post-health.json"
docker logs "$container" >"$root/server.log" 2>&1

python3 - "$root/performance.json" "$root/canaries.json" "$root/qualification.json" "$reference_performance" <<'PY'
import json,pathlib,sys
p=json.load(open(sys.argv[1])); c=json.load(open(sys.argv[2])); g=p["realistic_final_gate"]
assert g["passed"] and p["fresh_response_validity"]["performance_gate_eligible"]
assert g["cached_tokens_all_zero"] and len(p["rows"]) == 12 and c["pass_all"]
assert len(set(p["prompt_sha256s"])) == 12
metric=p["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
reference_path=sys.argv[4]
reference_identical=None
if reference_path:
    reference=json.load(open(reference_path))
    current={row["prompt_id"]:row["token_ids"] for row in p["rows"]}
    expected={row["prompt_id"]:row["token_ids"] for row in reference["rows"]}
    reference_identical=current == expected and len(current) == 12
    assert reference_identical
value={"status":"passed-candidate-not-promoted","strict_metric_tok_s":metric,
       "aggregation":"median-of-prompt-class-medians","prompt_count":12,
       "cached_tokens_all_zero":True,"canaries_passed":True,
       "repeat_8x_unique_outputs":c["repeat_8x"]["unique_outputs"],
       "reference_token_ids_identical":reference_identical,
       "promotion_authorized":False}
pathlib.Path(sys.argv[3]).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
print(json.dumps(value,indent=2,sort_keys=True))
PY

docker rm -f "$container" >/dev/null
if ss -ltn | grep -Eq ":${port}[[:space:]]"; then fail 'port remained occupied'; fi
if pgrep -af '[E]ngineCore|[v]llm serve.*qwen3.8-27b-int4-autoround' >/dev/null; then fail 'vLLM process remained'; fi
journalctl -k --since "@${journal_start}" --no-pager >"$root/kernel-journal.log"
if grep -Eqi 'xe .*reset|xe .*fault|xe .*timeout|xe .*timed out|xe .*fatal|xe .*wedged|device lost|out of memory|oom-kill|EXT4-fs error|I/O error' "$root/kernel-journal.log"; then
  fail 'new GPU, OOM, filesystem, or I/O fault event detected'
fi
printf 'PASS strict candidate evidence at %s\n' "$root"
