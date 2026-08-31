#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
hook="$script_dir/qwen38-loaded-model-hash-sitecustomize.py"
prereg="$repo/experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-loaded-model-hash-d8b-prereg.md"
model=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround
root=/mnt/fast-ai/bench-results/qwen38-loaded-model-hash-20260831-d8b
cache_root=/mnt/fast-ai/vllm-cache/qwen38-loaded-model-hash-20260831-d8b
image=neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1
image_id=sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136
fail(){ printf 'FAIL: %s\n' "$*" >&2; exit 1; }
container=
cleanup(){ local rc=$?; set +e; [[ -z "$container" ]] || docker rm -f "$container" >/dev/null 2>&1; exit "$rc"; }
trap cleanup EXIT; trap 'exit 130' INT TERM HUP
[[ -f "$hook" && -f "$prereg" && ! -e "$root" && ! -e "$cache_root" ]] || fail 'missing input or reused root'
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$image_id" ]] || fail 'image identity mismatch'
git -C "$repo" fetch origin main --quiet
[[ "$(git -C "$repo" rev-parse HEAD)" == "$(git -C "$repo" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail 'repository must be clean'
[[ -z "$(docker ps -q)" ]] || fail 'another container is running'
exec 7>/tmp/b70-benchmark.lock; flock -n 7 || fail 'benchmark lock held'
exec 8>/tmp/b70-gpu0.lock; flock -n 8 || fail 'GPU0 lock held'
mkdir -p "$root" "$cache_root"
"$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
 "$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json" "$model" \
 --json "$root/model-verify.json" >"$root/model-verify.log"
for process in 1 2 3 4; do
  cache="$cache_root/process-${process}"; mkdir "$cache"
  container="q38-model-hash-d8b-${process}"
  docker run -d --name "$container" --ulimit core=0 --memory 12g --memory-swap 36g \
    --device /dev/dri:/dev/dri --volume /dev/dri/by-path:/dev/dri/by-path:ro \
    --group-add video --group-add render --security-opt label=disable --ipc=host --shm-size=16g \
    --volume "$model:/model:ro" --volume "$cache:/run-cache" --volume "$root:/out" \
    --volume "$hook:/instrument/sitecustomize.py:ro" \
    --env PYTHONPATH=/instrument --env VLLM_XPU_LOADED_MODEL_HASH_OUT="/out/process-${process}.json" \
    --env ZE_AFFINITY_MASK=0 --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    --env VLLM_TARGET_DEVICE=xpu --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
    --env VLLM_NO_USAGE_STATS=1 --env PYTHONHASHSEED=0 \
    --env VLLM_XPU_ENABLE_XPU_GRAPH=0 --env VLLM_XPU_GRAPH=0 \
    --env VLLM_XPU_FP8_BLOCK_W8A16=0 --env VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=1 \
    --env VLLM_CACHE_ROOT=/run-cache/vllm --env XDG_CACHE_HOME=/run-cache/xdg \
    "$image" --model /model --tokenizer /model --served-model-name qwen38-model-hash-d8 \
    --host 0.0.0.0 --port 8000 --trust-remote-code --tensor-parallel-size 1 \
    --dtype float16 --kv-cache-dtype auto --gpu-memory-utilization 0.80 \
    --max-model-len 1024 --block-size 64 --max-num-seqs 1 --max-num-batched-tokens 1024 \
    --no-enable-prefix-caching --language-model-only --enforce-eager \
    >"$root/process-${process}.container-id"
  deadline=$((SECONDS+900))
  until [[ -s "$root/process-${process}.json" ]]; do
    [[ "$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || true)" == true ]] || {
      docker logs "$container" >"$root/process-${process}.log" 2>&1 || true; fail "process ${process} exited before receipt";
    }
    (( SECONDS < deadline )) || fail "process ${process} hash timeout"
    sleep 2
  done
  docker logs "$container" >"$root/process-${process}.log" 2>&1 || true
  docker rm -f "$container" >/dev/null; container=
done
python3 - "$root" "$prereg" "$image" "$image_id" <<'PY'
import datetime as dt,hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); prereg=pathlib.Path(sys.argv[2]); image,image_id=sys.argv[3:]
docs=[json.loads((root/f"process-{i}.json").read_text()) for i in range(1,5)]
names=sorted(docs[0]["tensors"])
if any(sorted(d["tensors"])!=names for d in docs): raise SystemExit("loaded tensor name sets differ")
different=[]
for name in names:
 values=[d["tensors"][name] for d in docs]
 if any(v!=values[0] for v in values[1:]): different.append(name)
passed=not different
result={"schema":"neural.download.qwen38-loaded-model-hashes.result.v1","created_utc":dt.datetime.now(dt.UTC).isoformat(),
 "classification":"negative-causal-screen" if passed else "positive-causal-finding","image":image,"image_id":image_id,
 "fresh_processes":4,"tensor_count":len(names),"passed":passed,"different_tensors":different,
 "process_sha256":{f"process-{i}":hashlib.sha256((root/f"process-{i}.json").read_bytes()).hexdigest() for i in range(1,5)},
 "model_verify_sha256":hashlib.sha256((root/"model-verify.json").read_bytes()).hexdigest(),
 "preregistration_sha256":hashlib.sha256(prereg.read_bytes()).hexdigest()}
(root/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True))
if not passed: raise SystemExit(3)
PY
