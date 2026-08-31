#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
hook="$script_dir/qwen38-final-hidden-trace-sitecustomize.py"
prereg="$repo/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-final-hidden-trace-d9-prereg.md"
suite="$repo/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
bench="$repo/scripts/bench-openai-realistic-suite.py"
model=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround
root=/mnt/fast-ai/bench-results/qwen38-final-hidden-trace-20260831-d9
cache_root=/mnt/fast-ai/vllm-cache/qwen38-final-hidden-trace-20260831-d9
image=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
image_id=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136
served=qwen38-final-hidden-d9
fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }
container=
active_dir=
cleanup(){
  local rc=$?; set +e
  if [[ -n "$container" ]]; then
    [[ -z "$active_dir" ]] || docker logs "$container" >"$active_dir/server.log" 2>&1 || true
    docker rm -f "$container" >/dev/null 2>&1 || true
  fi
  exit "$rc"
}
trap cleanup EXIT; trap 'exit 130' INT TERM HUP
[[ -f "$hook" && -f "$prereg" && -f "$suite" && -f "$bench" ]] || fail 'missing frozen input'
[[ -d "$model" && ! -L "$model" ]] || fail 'model must be a local real directory'
[[ "$(findmnt -n -o FSTYPE -T "$model")" == ext4 ]] || fail 'model must be on local ext4'
[[ ! -e "$root" && ! -e "$cache_root" ]] || fail 'output or cache root already exists'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'
[[ -z "$(docker ps -q)" ]] || fail 'another container is running'
! pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server' >/dev/null || fail 'another model server is running'
exec 7>/tmp/b70-benchmark.lock; flock -n 7 || fail 'benchmark lock held'
exec 8>/tmp/b70-gpu0.lock; flock -n 8 || fail 'GPU0 lock held'
mkdir -p "$root" "$cache_root"
sha256sum "$hook" "$prereg" "$suite" "$bench" >"$root/input-sha256sums.txt"
"$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
  "$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json" "$model" \
  --json "$root/model-verify.json" >"$root/model-verify.log"

for process in 1 2 3 4; do
  port=$((18189 + process))
  active_dir="$root/process-${process}"; cache="$cache_root/process-${process}"
  mkdir "$active_dir" "$cache"
  container="q38-final-hidden-d9-${process}"
  docker run -d --name "$container" --ulimit core=0 --memory 12g --memory-swap 36g \
    --device /dev/dri:/dev/dri --volume /dev/dri/by-path:/dev/dri/by-path:ro \
    --group-add video --group-add render --security-opt label=disable --ipc=host --shm-size=16g \
    --publish "127.0.0.1:${port}:8000" --volume "$model:/model:ro" \
    --volume "$cache:/run-cache" --volume "$active_dir:/out" \
    --volume "$hook:/instrument/sitecustomize.py:ro" --env PYTHONPATH=/instrument \
    --env VLLM_XPU_FINAL_HIDDEN_TRACE_OUT=/out/trace.json \
    --env VLLM_XPU_FINAL_HIDDEN_TRACE_CALL=60 \
    --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    --env VLLM_TARGET_DEVICE=xpu --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
    --env VLLM_NO_USAGE_STATS=1 --env PYTHONHASHSEED=0 \
    --env VLLM_XPU_ENABLE_XPU_GRAPH=0 --env VLLM_XPU_GRAPH=0 \
    --env VLLM_XPU_FP8_BLOCK_W8A16=0 --env VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=1 \
    --env VLLM_CACHE_ROOT=/run-cache/vllm --env XDG_CACHE_HOME=/run-cache/xdg \
    --env PYTORCH_ALLOC_CONF=expandable_segments:True --env CCL_ZE_IPC_EXCHANGE=sockets \
    "$image" /model --host 0.0.0.0 --port 8000 --trust-remote-code \
    --served-model-name "$served" --tensor-parallel-size 1 --pipeline-parallel-size 1 \
    --data-parallel-size 1 --dtype float16 --kv-cache-dtype auto \
    --gpu-memory-utilization 0.80 --max-model-len 1024 --block-size 64 \
    --max-num-seqs 1 --max-num-batched-tokens 1024 --no-enable-prefix-caching \
    --enable-prompt-tokens-details --language-model-only --enforce-eager \
    >"$active_dir/container-id.txt"
  deadline=$((SECONDS+900))
  until curl -fsS "http://127.0.0.1:${port}/health" >"$active_dir/health.json" 2>"$active_dir/health.err"; do
    [[ "$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || true)" == true ]] || {
      docker logs "$container" >&2 || true; fail "process ${process} exited before readiness";
    }
    (( SECONDS < deadline )) || fail "process ${process} readiness timeout"
    sleep 3
  done
  docker logs "$container" >"$active_dir/server-startup.log" 2>&1
  [[ "$(docker inspect --format '{{.Image}}' "$container")" == "$image_id" ]] || fail 'image receipt mismatch'
  python3 "$bench" --base-url "http://127.0.0.1:${port}" --model "$served" \
    --api-mode completions --suite "$suite" --prompt-id sql-debugging \
    --max-tokens 64 --metric-tokens 32 --seed 42 --timeout 900 --return-token-ids \
    --allow-screening --request-extra-json '{"temperature":0,"top_p":1}' \
    --out "$active_dir/performance.json" >"$active_dir/performance.stdout"
  [[ -s "$active_dir/trace.json" ]] || fail "process ${process} did not reach trace call 60"
  curl -fsS "http://127.0.0.1:${port}/health" >"$active_dir/post-health.json"
  docker logs "$container" >"$active_dir/server.log" 2>&1
  docker rm -f "$container" >/dev/null; container=
  [[ -z "$(ss -ltnH "sport = :$port")" ]] || fail "process ${process} port remained occupied"
done

python3 - "$root" "$prereg" "$image_id" <<'PY'
import datetime as dt, hashlib, json, pathlib, sys
root=pathlib.Path(sys.argv[1]); prereg=pathlib.Path(sys.argv[2]); image_id=sys.argv[3]
traces=[json.loads((root/f"process-{i}"/"trace.json").read_text()) for i in range(1,5)]
perfs=[json.loads((root/f"process-{i}"/"performance.json").read_text()) for i in range(1,5)]
tokens=[p["rows"][0]["token_ids"] for p in perfs]
limit=min(map(len,tokens)); first_diff=next((i for i in range(limit) if len({t[i] for t in tokens})>1),None)
if first_diff is None and len({len(t) for t in tokens})>1: first_diff=limit
input_ids_identical=len({json.dumps(t["input_ids"],sort_keys=True) for t in traces})==1
positions_identical=len({json.dumps(t["positions"],sort_keys=True) for t in traces})==1
hidden_identical=len({json.dumps(t["hidden_states"],sort_keys=True) for t in traces})==1
outputs_identical=len({tuple(t) for t in tokens})==1
if not input_ids_identical or not positions_identical:
 classification="invalid-localization-inputs-differed"
elif not hidden_identical:
 classification="positive-causal-finding-final-hidden"
elif not outputs_identical:
 classification="positive-causal-finding-post-model"
else:
 classification="negative-inconclusive-no-branch"
result={"schema":"neural.download.qwen38-final-hidden-trace.result.v1",
 "created_utc":dt.datetime.now(dt.UTC).isoformat(),"classification":classification,
 "image_id":image_id,"fresh_processes":4,"target_call_index":60,
 "input_ids_identical":input_ids_identical,"positions_identical":positions_identical,
 "final_hidden_identical":hidden_identical,"outputs_identical":outputs_identical,
 "first_output_difference_zero_based":first_diff,
 "token_ids_at_first_difference":None if first_diff is None else [t[first_diff] if first_diff<len(t) else None for t in tokens],
 "trace_sha256":{f"process-{i}":hashlib.sha256((root/f"process-{i}"/"trace.json").read_bytes()).hexdigest() for i in range(1,5)},
 "output_sha256":{f"process-{i}":hashlib.sha256(json.dumps(tokens[i-1],separators=(',',':')).encode()).hexdigest() for i in range(1,5)},
 "preregistration_sha256":hashlib.sha256(prereg.read_bytes()).hexdigest()}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps(result,indent=2,sort_keys=True))
if classification.startswith("invalid-"): raise SystemExit(3)
PY
