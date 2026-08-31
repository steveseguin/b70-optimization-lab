#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
prereg="$repo/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-official-f01e-tp1-eager-control-c1-prereg.md"
model=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
suite="$repo/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
bench="$repo/scripts/bench-openai-realistic-suite.py"
canaries="$repo/scripts/neural-download-canaries.py"
image='vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f'
image_id=sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
vllm_head=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
served=qwen38-official-f01e-tp1-eager-c1
root=/mnt/fast-ai/bench-results/qwen38-official-f01e-tp1-eager-control-20260831-c1
cache_root=/mnt/fast-ai/vllm-cache/qwen38-official-f01e-tp1-eager-control-20260831-c1

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
container=
cleanup() {
  local rc=$?
  set +e
  if [[ -n "$container" ]]; then
    docker logs "$container" >"$active_dir/server.log" 2>&1 || true
    docker inspect "$container" >"$active_dir/container-inspect.json" 2>/dev/null || true
    docker rm -f "$container" >/dev/null 2>&1 || true
    container=
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

[[ -f "$prereg" && -f "$suite" && -f "$bench" && -f "$canaries" ]] || fail 'missing frozen input'
[[ -d "$model" && ! -L "$model" ]] || fail 'model must be a real local directory'
[[ "$(findmnt -n -o FSTYPE -T "$model")" == ext4 ]] || fail 'model must be on local ext4'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'official image identity mismatch'
[[ ! -e "$root" && ! -e "$cache_root" ]] || fail 'output or cache root already exists'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'
[[ -z "$(docker ps -q)" ]] || fail 'another container is running'
! pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server' >/dev/null || fail 'another model server is running'
(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo) >= 8 * 1024 * 1024 )) || fail 'less than 8 GiB host memory available'

exec 7>/tmp/b70-benchmark.lock
flock -n 7 || fail 'benchmark lock held'
exec 8>/tmp/b70-gpu0.lock
flock -n 8 || fail 'GPU0 lock held'
mkdir -p "$root" "$cache_root"
sha256sum "$prereg" "$suite" "$bench" "$canaries" "$model_manifest" "$model_verifier" >"$root/input-sha256sums.txt"

run_arm() {
  local arm=$1 port=$2
  active_dir="$root/$arm"
  local cache="$cache_root/$arm"
  container="q38-f01e-tp1-eager-c1-${arm}"
  mkdir "$active_dir" "$cache"
  "$model_verifier" "$model_manifest" "$model" --json "$active_dir/model-verify.json" >"$active_dir/model-verify.log"
  docker run -d --name "$container" --ulimit core=0 --memory 12g --memory-swap 36g \
    --device /dev/dri:/dev/dri --group-add render --security-opt label=disable \
    --ipc=host --shm-size=16g --publish "127.0.0.1:${port}:8000" \
    --volume "$model:/model:ro" --volume "$cache:/run-cache" \
    --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    --env VLLM_TARGET_DEVICE=xpu --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
    --env VLLM_NO_USAGE_STATS=1 --env PYTHONHASHSEED=0 \
    --env VLLM_XPU_ENABLE_XPU_GRAPH=0 --env VLLM_XPU_GRAPH=0 \
    --env VLLM_CACHE_ROOT=/run-cache/vllm --env XDG_CACHE_HOME=/run-cache/xdg \
    --env PYTORCH_ALLOC_CONF=expandable_segments:True \
    --env CCL_ZE_IPC_EXCHANGE=sockets \
    "$image" /model --host 0.0.0.0 --port 8000 --trust-remote-code \
    --served-model-name "$served" --tensor-parallel-size 1 --pipeline-parallel-size 1 \
    --data-parallel-size 1 --dtype float16 --kv-cache-dtype auto \
    --gpu-memory-utilization 0.80 --max-model-len 1024 --block-size 64 \
    --max-num-seqs 1 --max-num-batched-tokens 1024 \
    --no-enable-prefix-caching --enable-prompt-tokens-details \
    --language-model-only --enforce-eager >"$active_dir/container-id.txt"

  local deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:${port}/health" >"$active_dir/health.json" 2>"$active_dir/health.err"; do
    [[ "$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || true)" == true ]] || {
      docker logs "$container" >&2 || true; fail "$arm server exited before readiness";
    }
    (( SECONDS < deadline )) || fail "$arm readiness timeout"
    sleep 3
  done
  docker logs "$container" >"$active_dir/server-startup.log" 2>&1
  docker inspect "$container" >"$active_dir/container-inspect.json"
  [[ "$(docker inspect --format '{{.Image}}' "$container")" == "$image_id" ]] || fail "$arm image receipt mismatch"
  [[ "$(docker exec "$container" git -C /workspace/vllm rev-parse HEAD)" == "$vllm_head" ]] || fail "$arm vLLM source mismatch"
  docker exec "$container" python3 -c 'import importlib.metadata as m; print(m.version("vllm")); print(m.version("vllm-xpu-kernels"))' >"$active_dir/stack-versions.txt"
  grep -Fxq '0.27.2rc1.dev77+gac7509e2b.xpu' "$active_dir/stack-versions.txt" || fail "$arm vLLM package mismatch"
  grep -Fxq '0.1.12.3' "$active_dir/stack-versions.txt" || fail "$arm XPU-kernel package mismatch"
  grep -Fq 'quantization=inc' "$active_dir/server-startup.log" || fail "$arm quantization marker missing"
  grep -Fq 'enforce_eager=True' "$active_dir/server-startup.log" || fail "$arm eager marker missing"
  ! grep -Fq 'Graph capturing finished' "$active_dir/server-startup.log" || fail "$arm unexpectedly captured a graph"
  curl -fsS "http://127.0.0.1:${port}/v1/models" >"$active_dir/models.json"

  python3 "$bench" --base-url "http://127.0.0.1:${port}" --model "$served" \
    --api-mode completions --suite "$suite" --max-tokens 512 --metric-tokens 100 \
    --seed 42 --timeout 900 --return-token-ids --require-natural-eos \
    --request-extra-json '{"temperature":0,"top_p":1}' --out "$active_dir/performance.json" \
    >"$active_dir/performance.stdout"
  python3 "$canaries" --base-url "http://127.0.0.1:${port}" --model "$served" \
    --out "$active_dir/canaries.json" >"$active_dir/canaries.stdout"
  python3 - "$active_dir/performance.json" "$active_dir/canaries.json" "$active_dir/qualification.json" <<'PY'
import json, pathlib, sys
p=json.load(open(sys.argv[1])); c=json.load(open(sys.argv[2])); g=p["realistic_final_gate"]
assert g["passed"] and p["fresh_response_validity"]["performance_gate_eligible"]
assert g["cached_tokens_all_zero"] and len(p["rows"]) == 12 and c["pass_all"]
assert all(len(row["token_ids"]) >= 100 for row in p["rows"])
metric=p["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
pathlib.Path(sys.argv[3]).write_text(json.dumps({"status":"passed","strict_metric_tok_s":metric,
 "prompt_count":12,"canaries_passed":True,"promotion_authorized":False},indent=2)+"\n")
PY
  curl -fsS "http://127.0.0.1:${port}/health" >"$active_dir/post-health.json"
  docker rm -f "$container" >/dev/null
  container=
  [[ -z "$(ss -ltnH "sport = :$port")" ]] || fail "$arm port remained occupied"
  ! pgrep -af '[E]ngineCore|[v]llm serve.*qwen3.8-27b-int4' >/dev/null || fail "$arm vLLM process survived cleanup"
}

journal_start=$(date +%s)
run_arm official-A 18176
run_arm official-B 18177
journalctl -k --since "@${journal_start}" --no-pager >"$root/kernel-journal.log"
if grep -Eqi 'xe .*reset|xe .*fault|xe .*timeout|xe .*timed out|xe .*fatal|xe .*wedged|device lost|out of memory|oom-kill' "$root/kernel-journal.log"; then
  fail 'new GPU/kernel/OOM fault event detected'
fi
python3 - "$root" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt, hashlib, json, pathlib, sys
root=pathlib.Path(sys.argv[1]); prereg=pathlib.Path(sys.argv[2]); image,image_id=sys.argv[3:]
arms={name:json.loads((root/name/"performance.json").read_text()) for name in ("official-A","official-B")}
rows={name:{row["prompt_id"]:row["token_ids"] for row in doc["rows"]} for name,doc in arms.items()}
ids=sorted(rows["official-A"])
assert ids == sorted(rows["official-B"]) and len(ids)==12
mismatch=[key for key in ids if rows["official-A"][key] != rows["official-B"][key]]
rates={name:doc["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"] for name,doc in arms.items()}
result={"schema":"neural.download.qwen38-official-f01e-tp1-eager-control.v1",
 "created_utc":dt.datetime.now(dt.UTC).isoformat(),"classification":"passed-exact-control" if not mismatch else "failed-exact-control",
 "image":image,"image_id":image_id,"tensor_parallel":1,"physical_gpus":[0],"execution_mode":"eager","mtp_depth":0,
 "exact_repeat":{"exact":12-len(mismatch),"total":12,"mismatching_prompt_ids":mismatch},"strict_rates_tok_s":rates,
 "performance_sha256":{name:hashlib.sha256((root/name/"performance.json").read_bytes()).hexdigest() for name in arms},
 "preregistration_sha256":hashlib.sha256(prereg.read_bytes()).hexdigest(),"promotion_authorized":False}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps(result,indent=2,sort_keys=True))
if mismatch: raise SystemExit(3)
PY
