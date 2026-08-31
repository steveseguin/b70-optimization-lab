#!/usr/bin/env bash
set -euo pipefail
: "${CAMPAIGN_ID:?set CAMPAIGN_ID}"
: "${TARGET_LAYER:?set TARGET_LAYER}"
: "${PREREG_PATH:?set PREREG_PATH}"
: "${TARGET_CALL:=60}"
[[ "$CAMPAIGN_ID" =~ ^[a-z0-9-]+$ ]] || { echo 'invalid CAMPAIGN_ID' >&2; exit 2; }
[[ "$TARGET_LAYER" =~ ^([0-9]|[1-5][0-9]|6[0-3])$ ]] || { echo 'invalid TARGET_LAYER' >&2; exit 2; }
[[ "$TARGET_CALL" =~ ^[0-9]+$ ]] || { echo 'invalid TARGET_CALL' >&2; exit 2; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
: "${TRACE_HOOK_NAME:=qwen38-decoder-layer-trace-sitecustomize.py}"
hook="$script_dir/$TRACE_HOOK_NAME"
prereg="$repo/$PREREG_PATH"
suite="$repo/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
bench="$repo/scripts/bench-openai-realistic-suite.py"
model=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround
root="/mnt/fast-ai/bench-results/${CAMPAIGN_ID}"
cache_root="/mnt/fast-ai/vllm-cache/${CAMPAIGN_ID}"
: "${TRACE_IMAGE:=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1}"
: "${TRACE_IMAGE_ID:=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136}"
image=$TRACE_IMAGE
image_id=$TRACE_IMAGE_ID
served=qwen38-layer-trace
fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }
container=; active_dir=
cleanup(){ local rc=$?; set +e; [[ -z "$container" ]] || docker rm -f "$container" >/dev/null 2>&1; exit "$rc"; }
trap cleanup EXIT; trap 'exit 130' INT TERM HUP
[[ -f "$hook" && -f "$prereg" && -f "$suite" && -f "$bench" ]] || fail 'missing frozen input'
[[ -d "$model" && ! -L "$model" && "$(findmnt -n -o FSTYPE -T "$model")" == ext4 ]] || fail 'model must be local ext4'
[[ ! -e "$root" && ! -e "$cache_root" ]] || fail 'output or cache root already exists'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" && -z "$(docker ps -q)" ]] || fail 'dirty repository or active container'
! pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server' >/dev/null || fail 'another model server is running'
exec 7>/tmp/b70-benchmark.lock; flock -n 7 || fail 'benchmark lock held'
exec 8>/tmp/b70-gpu0.lock; flock -n 8 || fail 'GPU0 lock held'
mkdir -p "$root" "$cache_root"
sha256sum "$hook" "$prereg" "$suite" "$bench" >"$root/input-sha256sums.txt"
"$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
  "$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json" "$model" \
  --json "$root/model-verify.json" >"$root/model-verify.log"
for process in 1 2 3 4; do
  port=$((18209 + process)); active_dir="$root/process-${process}"; cache="$cache_root/process-${process}"
  mkdir "$active_dir" "$cache"; container="q38-layer-trace-${TARGET_LAYER}-${process}"
  docker run -d --name "$container" --ulimit core=0 --memory 12g --memory-swap 36g \
    --device /dev/dri:/dev/dri --volume /dev/dri/by-path:/dev/dri/by-path:ro \
    --group-add video --group-add render --security-opt label=disable --ipc=host --shm-size=16g \
    --publish "127.0.0.1:${port}:8000" --volume "$model:/model:ro" \
    --volume "$cache:/run-cache" --volume "$active_dir:/out" \
    --volume "$hook:/instrument/sitecustomize.py:ro" --env PYTHONPATH=/instrument \
    --env VLLM_XPU_DECODER_LAYER_TRACE_OUT=/out/trace.json \
    --env VLLM_XPU_DECODER_LAYER_TRACE_CALL="$TARGET_CALL" --env VLLM_XPU_DECODER_LAYER_TRACE_LAYER="$TARGET_LAYER" \
    --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    --env VLLM_TARGET_DEVICE=xpu --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
    --env VLLM_NO_USAGE_STATS=1 --env PYTHONHASHSEED=0 \
    --env VLLM_XPU_ENABLE_XPU_GRAPH=0 --env VLLM_XPU_GRAPH=0 \
    --env VLLM_XPU_FP8_BLOCK_W8A16=0 --env VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=1 \
    --env VLLM_CACHE_ROOT=/run-cache/vllm --env XDG_CACHE_HOME=/run-cache/xdg \
    --env PYTORCH_ALLOC_CONF=expandable_segments:True --env CCL_ZE_IPC_EXCHANGE=sockets \
    "$image" /model --host 0.0.0.0 --port 8000 --trust-remote-code --served-model-name "$served" \
    --tensor-parallel-size 1 --pipeline-parallel-size 1 --data-parallel-size 1 \
    --dtype float16 --kv-cache-dtype auto --gpu-memory-utilization 0.80 \
    --max-model-len 1024 --block-size 64 --max-num-seqs 1 --max-num-batched-tokens 1024 \
    --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only --enforce-eager \
    >"$active_dir/container-id.txt"
  deadline=$((SECONDS+900))
  until curl -fsS "http://127.0.0.1:${port}/health" >"$active_dir/health.json" 2>"$active_dir/health.err"; do
    [[ "$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || true)" == true ]] || { docker logs "$container" >&2 || true; fail "process $process exited"; }
    (( SECONDS < deadline )) || fail "process $process readiness timeout"; sleep 3
  done
  docker logs "$container" >"$active_dir/server-startup.log" 2>&1
  [[ "$(docker inspect --format '{{.Image}}' "$container")" == "$image_id" ]] || fail 'image receipt mismatch'
  python3 "$bench" --base-url "http://127.0.0.1:${port}" --model "$served" \
    --api-mode completions --suite "$suite" --prompt-id sql-debugging --max-tokens 64 \
    --metric-tokens 32 --seed 42 --timeout 900 --return-token-ids --allow-screening \
    --request-extra-json '{"temperature":0,"top_p":1}' --out "$active_dir/performance.json" \
    >"$active_dir/performance.stdout"
  if [[ ! -s "$active_dir/trace.json" ]]; then
    docker logs "$container" >"$active_dir/server.log" 2>&1 || true
    fail "process $process did not reach trace"
  fi
  docker logs "$container" >"$active_dir/server.log" 2>&1
  docker rm -f "$container" >/dev/null; container=
done
python3 - "$root" "$prereg" "$image_id" "$TARGET_LAYER" "$TARGET_CALL" <<'PY'
import datetime as dt,hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); prereg=pathlib.Path(sys.argv[2]); image_id=sys.argv[3]; layer=int(sys.argv[4]); target_call=int(sys.argv[5])
traces=[json.loads((root/f"process-{i}"/"trace.json").read_text()) for i in range(1,5)]
tokens=[json.loads((root/f"process-{i}"/"performance.json").read_text())["rows"][0]["token_ids"] for i in range(1,5)]
limit=min(map(len,tokens)); first=next((i for i in range(limit) if len({t[i] for t in tokens})>1),None)
positions_identical=len({json.dumps(t["positions"],sort_keys=True) for t in traces})==1
hidden_identical=len({json.dumps(t["hidden_states"],sort_keys=True) for t in traces})==1
residual_identical=len({json.dumps(t["residual"],sort_keys=True) for t in traces})==1
pair_identical=hidden_identical and residual_identical
classification=("invalid-localization" if not positions_identical or (first is not None and first<target_call)
 else "positive-causal-finding-at-or-before-layer" if not pair_identical
 else "negative-bound-after-layer")
result={"schema":"neural.download.qwen38-decoder-layer-trace.result.v1","created_utc":dt.datetime.now(dt.UTC).isoformat(),
 "classification":classification,"image_id":image_id,"target_layer":layer,"target_call_index":target_call,"fresh_processes":4,
 "positions_identical":positions_identical,"hidden_states_identical":hidden_identical,"residual_identical":residual_identical,
 "layer_output_pair_identical":pair_identical,"first_output_difference_zero_based":first,
 "token_ids_at_target":[t[target_call] for t in tokens],
 "trace_sha256":{f"process-{i}":hashlib.sha256((root/f"process-{i}"/"trace.json").read_bytes()).hexdigest() for i in range(1,5)},
 "preregistration_sha256":hashlib.sha256(prereg.read_bytes()).hexdigest()}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True))
if classification.startswith('invalid-'): raise SystemExit(3)
PY
