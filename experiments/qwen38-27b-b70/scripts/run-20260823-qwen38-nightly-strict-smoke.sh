#!/usr/bin/env bash
set -uo pipefail

# Opt-in fresh-cache smoke/final runner for the pinned Qwen3.8 XPU nightly.
# The historical 2026-08-22 diagnostic runner is intentionally unchanged.
#
# Usage: run-20260823-qwen38-nightly-strict-smoke.sh \
#   MTP KV MAXLEN GPUS PORT OUT_DIR SUITE CACHE_DIR
#
# Required CACHE_POLICY:
#   fresh  CACHE_DIR must not exist and must live on ext4.
#   replay CACHE_DIR must exist; EXPECTED_CACHE_MANIFEST_SHA256 is required.
#
# Useful environment:
#   SUDO_PASS_FILE, EXTRA_VLLM_ARGS, GPU_MEM_UTIL, VLLM_XPU_GRAPH
#   PYTHONHASHSEED, VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE
#   VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING, TRITON_CACHE_AUTOTUNING
#   PROMPT_IDS (comma-separated), MAX_TOKENS (default 128), BENCH (default 1)
#   CANARY (default 1), NATURAL_EOS (default 0), RETURN_TOKEN_IDS (default 1)

readonly image_tag="vllm/vllm-openai-xpu:nightly-e9d1398d9edfd90fcc1cf783805240e3effec013"
readonly image_digest="sha256:bc979d1ba312dc8a666c57a40205f35d7fc5d96b2f7450c2c77f5b3d5243f0e0"
readonly image_ref="vllm/vllm-openai-xpu@${image_digest}"

mtp=${1:?}; kv=${2:?}; maxlen=${3:?}; gpu=${4:?}; port=${5:?}
out=${6:?}; suite=${7:?}; cache_dir=${8:?}
tp=$(( $(tr -dc ',' <<< "$gpu" | wc -c) + 1 ))
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
venv=/home/steve/.venvs/vllm-xpu
alias=qwen38-tp-strict
name="qwen38-nightly-strict-${port}"
cache_policy=${CACHE_POLICY:?set CACHE_POLICY=fresh or replay}

dockerc() {
  if [[ -n "${SUDO_PASS_FILE:-}" ]]; then
    sudo -S -p '' docker "$@" < "$SUDO_PASS_FILE"
  else
    docker "$@"
  fi
}

fail() {
  echo "error: $*" >&2
  exit 1
}

cache_manifest() {
  local destination=$1
  (
    cd "$cache_dir" || exit 1
    find . -type f -print0 | sort -z | xargs -0 -r sha256sum
  ) > "$destination"
}

[[ "$cache_policy" == "fresh" || "$cache_policy" == "replay" ]] || \
  fail "CACHE_POLICY must be fresh or replay"
[[ -f "$suite" ]] || fail "missing suite: $suite"
[[ ! -e "$out" ]] || fail "strict output already exists: $out"
[[ -z "$(git -C "$repo" status --porcelain)" ]] || fail "lab repo must be clean"
if dockerc ps --format '{{.Names}}' | grep -qx "$name"; then
  fail "container $name already running"
fi
pgrep -af 'EngineCore|vllm serve' | grep -v pgrep >/dev/null && \
  fail "a host vLLM server is already running"

cache_parent=$(dirname -- "$cache_dir")
mkdir -p "$cache_parent"
cache_fstype=$(findmnt -n -o FSTYPE -T "$cache_parent")
[[ "$cache_fstype" == "ext4" ]] || fail "strict cache must be on ext4, got $cache_fstype"
if [[ "$cache_policy" == "fresh" ]]; then
  [[ ! -e "$cache_dir" ]] || fail "fresh cache already exists: $cache_dir"
  mkdir "$cache_dir"
else
  [[ -d "$cache_dir" ]] || fail "replay cache is missing: $cache_dir"
  [[ -n "${EXPECTED_CACHE_MANIFEST_SHA256:-}" ]] || \
    fail "replay requires EXPECTED_CACHE_MANIFEST_SHA256"
fi
mkdir "$out"
cp "$suite" "$out/validation-suite.json"

local_identity=$(dockerc image inspect --format '{{.Id}}' "$image_tag") || \
  fail "pinned image is unavailable"
[[ "$local_identity" == "$image_digest" ]] || \
  fail "image identity mismatch: $local_identity"
dockerc image inspect "$image_ref" > "$out/image-inspect.json" || \
  fail "immutable image reference is unavailable"
printf '%s\n' "$local_identity" > "$out/image-id.txt"

if [[ "$cache_policy" == "replay" ]]; then
  cache_manifest "$out/cache-manifest.pre.sha256"
  actual_manifest_sha=$(sha256sum "$out/cache-manifest.pre.sha256" | awk '{print $1}')
  [[ "$actual_manifest_sha" == "$EXPECTED_CACHE_MANIFEST_SHA256" ]] || \
    fail "replay cache manifest mismatch"
fi

args=( "$model" --host 0.0.0.0 --port 8000 --trust-remote-code
  --served-model-name "$alias" --tensor-parallel-size "$tp"
  --max-model-len "$maxlen" --max-num-seqs 1 --max-num-batched-tokens 1024
  --gpu-memory-utilization "${GPU_MEM_UTIL:-0.90}" --dtype float16
  --reasoning-parser qwen3
  --default-chat-template-kwargs '{"enable_thinking": false}'
  --enable-prompt-tokens-details --no-enable-prefix-caching )
[[ "$kv" != "f16" ]] && args+=( --kv-cache-dtype "$kv" )
[[ "$mtp" != "0" ]] && args+=(
  --speculative-config "{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":$mtp}"
)
[[ -n "${EXTRA_VLLM_ARGS:-}" ]] && args+=( ${EXTRA_VLLM_ARGS} )
printf '%s\n' "${args[@]}" > "$out/server-args.txt"

env_args=(
  -e CCL_ZE_IPC_EXCHANGE=sockets
  -e ZE_AFFINITY_MASK="$gpu"
  -e VLLM_NO_USAGE_STATS=1
  -e VLLM_CACHE_ROOT=/run-cache/vllm
  -e XDG_CACHE_HOME=/run-cache/xdg
)
for variable in VLLM_XPU_GRAPH PYTHONHASHSEED \
  VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE \
  VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING TRITON_CACHE_AUTOTUNING; do
  if [[ -n "${!variable:-}" ]]; then
    container_variable=$variable
    [[ "$variable" == "VLLM_XPU_GRAPH" ]] && \
      container_variable=VLLM_XPU_ENABLE_XPU_GRAPH
    env_args+=( -e "$container_variable=${!variable}" )
  fi
done

{
  echo "image_ref=$image_ref"
  echo "image_id=$local_identity"
  echo "cache_policy=$cache_policy"
  echo "cache_dir=$cache_dir"
  echo "tp=$tp"
  echo "gpus=$gpu"
  echo "mtp=$mtp"
  echo "kv=$kv"
  echo "max_model_len=$maxlen"
  echo "gpu_memory_utilization=${GPU_MEM_UTIL:-0.90}"
  echo "vllm_xpu_graph=${VLLM_XPU_GRAPH:-unset}"
  echo "pythonhashseed=${PYTHONHASHSEED:-unset}"
  echo "inductor_max_autotune=${VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE:-unset}"
  echo "inductor_coordinate_descent=${VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING:-unset}"
  echo "triton_cache_autotuning=${TRITON_CACHE_AUTOTUNING:-unset}"
  echo "natural_eos=${NATURAL_EOS:-0}"
  echo "return_token_ids=${RETURN_TOKEN_IDS:-1}"
  echo "prompt_ids=${PROMPT_IDS:-all}"
  echo "lab_git_head=$(git -C "$repo" rev-parse HEAD)"
} > "$out/identity.env"

cleanup() {
  local cleanup_rc=$?
  if [[ ! -f "$out/final.status" ]]; then
    echo "fail rc=$cleanup_rc" > "$out/final.status"
  fi
  dockerc logs "$name" > "$out/server.log" 2>&1 || true
  dockerc inspect "$name" > "$out/container-inspect.json" 2>/dev/null || true
  if [[ -d "$cache_dir" ]]; then
    cache_manifest "$out/cache-manifest.post.sha256" || true
    sha256sum "$out/cache-manifest.post.sha256" \
      > "$out/cache-manifest.post.sha256.digest" 2>/dev/null || true
  fi
  dockerc rm -f "$name" >/dev/null 2>&1 || true
  exit "$cleanup_rc"
}
trap cleanup EXIT

dockerc run -d --name "$name" \
  --device /dev/dri --group-add 44 --group-add 992 --ipc=host \
  -v /dev/dri/by-path:/dev/dri/by-path:ro \
  -v /mnt/usb-models:/mnt/usb-models \
  -v "$cache_dir:/run-cache" \
  -p "127.0.0.1:$port:8000" \
  "${env_args[@]}" --shm-size 16g \
  "$image_ref" "${args[@]}" > "$out/container-id.txt" || exit 2

healthy=0
for _ in $(seq 1 240); do
  if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  state=$(dockerc inspect --format '{{.State.Running}}' "$name" 2>/dev/null || echo false)
  [[ "$state" == "true" ]] || exit 2
  sleep 5
done
[[ "$healthy" == "1" ]] || exit 2
dockerc exec "$name" python3 -c \
  'import torch, transformers, triton, vllm; print("vllm", vllm.__version__); print("torch", torch.__version__); print("triton", triton.__version__); print("transformers", transformers.__version__)' \
  > "$out/stack-versions.txt" 2>&1 || true

if [[ "${CANARY:-1}" == "1" ]]; then
  "$venv/bin/python" - "http://127.0.0.1:$port" "$alias" "$out/canary.json" <<'PY'
import json, sys, urllib.request
base_url, model, destination = sys.argv[1:]
payload = {
    "model": model,
    "messages": [{"role": "user", "content": "What does this Python expression evaluate to? Answer only the integer: sum(i * i for i in range(4))"}],
    "max_tokens": 8,
    "temperature": 0,
    "top_p": 1,
    "seed": 20260609,
    "chat_template_kwargs": {"enable_thinking": False},
}
request = urllib.request.Request(
    f"{base_url}/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=900) as response:
    data = json.loads(response.read())
content = (data["choices"][0]["message"].get("content") or "").strip()
usage = data.get("usage") or {}
cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
result = {"content": content, "cached_tokens": cached, "response": data}
open(destination, "w").write(json.dumps(result, indent=2) + "\n")
if content != "14" or cached != 0:
    raise SystemExit(3)
PY
  canary_rc=$?
  echo "canary_rc=$canary_rc" > "$out/canary.status"
  [[ "$canary_rc" == "0" ]] || exit "$canary_rc"
fi

if [[ "${BENCH:-1}" == "1" ]]; then
  bench_args=(
    --base-url "http://127.0.0.1:$port" --model "$alias" --api-mode chat
    --suite "$suite" --max-tokens "${MAX_TOKENS:-128}" --metric-tokens 100
    --seed 1 --timeout 900 --out "$out/bench.json"
  )
  [[ "${RETURN_TOKEN_IDS:-1}" == "1" ]] && bench_args+=( --return-token-ids )
  if [[ -n "${PROMPT_IDS:-}" ]]; then
    IFS=',' read -r -a prompt_ids <<< "$PROMPT_IDS"
    for prompt_id in "${prompt_ids[@]}"; do
      bench_args+=( --prompt-id "$prompt_id" )
    done
  fi
  if [[ "${NATURAL_EOS:-0}" == "1" ]]; then
    bench_args+=( --require-natural-eos
      --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' )
  else
    bench_args+=(
      --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false},"ignore_eos":true}'
    )
  fi
  "$venv/bin/python" "$repo/scripts/bench-openai-realistic-suite.py" \
    "${bench_args[@]}" > "$out/bench.stdout.log" 2>&1
  bench_rc=$?
  echo "bench_rc=$bench_rc" > "$out/bench.status"
  [[ "$bench_rc" == "0" ]] || exit "$bench_rc"
fi

if [[ "$cache_policy" == "replay" ]]; then
  cache_manifest "$out/cache-manifest.replay-final.sha256"
  cmp -s "$out/cache-manifest.pre.sha256" "$out/cache-manifest.replay-final.sha256" || \
    exit 4
fi

echo "pass" > "$out/final.status"
