#!/usr/bin/env bash
set -euo pipefail

# Gemma 4 26B A4B vLLM/XPU int8-per-channel candidate runner.
# This is the secondary Gemma lane after llama.cpp Q8: one complete model
# replica per B70, no tensor-parallel split, no prefix-cache reuse.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU_INDEX="${GPU_INDEX:-0}"
ONEAPI_DEVICE_SELECTOR_VALUE="${ONEAPI_DEVICE_SELECTOR:-level_zero:*}"
PORT="${PORT:-18270}"
HOST="${HOST:-127.0.0.1}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
MODEL_ALIAS="${MODEL_ALIAS:-gemma4-26b-a4b-int8pc}"
MODEL="${MODEL:-/mnt/fast-ai/llm-cache/hf/models--google--gemma-4-26B-A4B-it/snapshots/20da991ab4afab98e8f910c4a2e8f4fbefc404ad}"
VLLM_BIN="${VLLM_BIN:-/home/steve/.venvs/vllm-xpu/bin/vllm}"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
DTYPE="${DTYPE:-bfloat16}"
QUANTIZATION="${QUANTIZATION:-int8_per_channel_weight_only}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
KV_CACHE_DTYPE="${KV_CACHE_DTYPE:-auto}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"
XPU_GRAPH="${XPU_GRAPH:-0}"
VLLM_XPU_ENABLE_XPU_GRAPH="${VLLM_XPU_ENABLE_XPU_GRAPH:-0}"
VLLM_XPU_FORCE_GRAPH_WITH_COMM="${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-0}"
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE="${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE:-0}"
COMPILATION_CONFIG="${COMPILATION_CONFIG:-}"
VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/mnt/fast-ai/vllm-cache-exp/gemma4-26b-a4b-it-int8pc-gpu${GPU_INDEX}}"
TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-${VLLM_CACHE_ROOT}/torchinductor}"
CANARY_REPEATS="${CANARY_REPEATS:-32}"
BENCH_REPEATS="${BENCH_REPEATS:-8}"
PROMPT_TOKENS="${PROMPT_TOKENS:-512}"
BENCH_PROMPT_MODE="${BENCH_PROMPT_MODE:-filled-long}"
MAX_TOKENS="${MAX_TOKENS:-512}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-1800}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LABEL="${LABEL:-gemma4-vllm-int8pc-gpu${GPU_INDEX}-ctx${MAX_MODEL_LEN}-mbt${MAX_NUM_BATCHED_TOKENS}-graph${VLLM_XPU_ENABLE_XPU_GRAPH}-${STAMP}}"
RUN_DIR="${RUN_DIR:-$ROOT/data/$LABEL}"
SERVER_OUT_DIR="${SERVER_OUT_DIR:-/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers}"
SERVER_LOG="$SERVER_OUT_DIR/${LABEL}.server.log"
SUMMARY_OUT="$RUN_DIR/summary.json"

mkdir -p "$RUN_DIR" "$SERVER_OUT_DIR" "$VLLM_CACHE_ROOT" "$TORCHINDUCTOR_CACHE_DIR"
VLLM_VERSION="$("$PYTHON" - <<'PY'
import pathlib
import vllm

print(vllm.__version__)
print(pathlib.Path(vllm.__file__).parent)
PY
)"
VLLM_VERSION_TEXT="$(printf '%s\n' "$VLLM_VERSION" | sed -n '1p')"
VLLM_SOURCE_PATH="$(printf '%s\n' "$VLLM_VERSION" | sed -n '2p')"

server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT"

if [[ ! -d "$MODEL" ]]; then
  echo "[gemma4-vllm] model snapshot missing: $MODEL" >&2
  exit 1
fi
"$PYTHON" - "$MODEL" <<'PY'
import json
import sys
from pathlib import Path

model = Path(sys.argv[1])
index_path = model / "model.safetensors.index.json"
if not index_path.exists():
    raise SystemExit(f"[gemma4-vllm] missing {index_path}")

index = json.loads(index_path.read_text())
shards = sorted(set(index.get("weight_map", {}).values()))
if not shards:
    shards = sorted(p.name for p in model.glob("model-*.safetensors"))

missing = []
for shard in shards:
    path = model / shard
    try:
        if not path.exists() or path.stat().st_size <= 0:
            missing.append(shard)
    except OSError:
        missing.append(shard)

incomplete = list(model.parent.parent.glob("blobs/*.incomplete"))
if missing or incomplete:
    details = []
    if missing:
        details.append(f"missing/unresolved shards={missing}")
    if incomplete:
        details.append(
            "active incomplete blobs="
            + ",".join(f"{p.name}:{p.stat().st_size}" for p in incomplete[:4])
        )
    raise SystemExit("[gemma4-vllm] incomplete model snapshot: " + "; ".join(details))

total = sum((model / shard).stat().st_size for shard in shards)
print(f"[gemma4-vllm] verified {len(shards)} shard(s), {total} bytes")
PY

echo "[gemma4-vllm] label=$LABEL"
echo "[gemma4-vllm] base_url=$BASE_URL"
echo "[gemma4-vllm] model=$MODEL"
echo "[gemma4-vllm] server_log=$SERVER_LOG"
echo "[gemma4-vllm] gpu=$GPU_INDEX port=$PORT ctx=$MAX_MODEL_LEN mbt=$MAX_NUM_BATCHED_TOKENS graph=$VLLM_XPU_ENABLE_XPU_GRAPH"

vllm_args=(
  serve "$MODEL"
  --host "$HOST"
  --port "$PORT"
  --served-model-name "$MODEL_ALIAS"
  --dtype "$DTYPE"
  --quantization "$QUANTIZATION"
  --tensor-parallel-size 1
  --pipeline-parallel-size 1
  --max-model-len "$MAX_MODEL_LEN"
  --max-num-batched-tokens "$MAX_NUM_BATCHED_TOKENS"
  --max-num-seqs "$MAX_NUM_SEQS"
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION"
  --kv-cache-dtype "$KV_CACHE_DTYPE"
  --no-enable-prefix-caching
  --language-model-only
  --generation-config vllm
)

if [[ -n "$COMPILATION_CONFIG" ]]; then
  vllm_args+=(--compilation-config "$COMPILATION_CONFIG")
fi
if [[ -n "$VLLM_EXTRA_ARGS" ]]; then
  # Keep this for simple scalar flags only.
  read -r -a extra_args <<< "$VLLM_EXTRA_ARGS"
  vllm_args+=("${extra_args[@]}")
fi

{
  echo "label=$LABEL"
  echo "model=$MODEL"
  echo "model_alias=$MODEL_ALIAS"
  echo "gpu_index=$GPU_INDEX"
  echo "port=$PORT"
  echo "dtype=$DTYPE"
  echo "quantization=$QUANTIZATION"
  echo "max_model_len=$MAX_MODEL_LEN"
  echo "max_num_batched_tokens=$MAX_NUM_BATCHED_TOKENS"
  echo "max_num_seqs=$MAX_NUM_SEQS"
  echo "gpu_memory_utilization=$GPU_MEMORY_UTILIZATION"
  echo "kv_cache_dtype=$KV_CACHE_DTYPE"
  echo "xpu_graph=$XPU_GRAPH"
  echo "vllm_xpu_enable_xpu_graph=$VLLM_XPU_ENABLE_XPU_GRAPH"
  echo "vllm_xpu_force_graph_with_comm=$VLLM_XPU_FORCE_GRAPH_WITH_COMM"
  echo "vllm_xpu_graph_noop_comm_capture=$VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE"
  echo "compilation_config=${COMPILATION_CONFIG:-<unset>}"
  echo "vllm_extra_args=${VLLM_EXTRA_ARGS:-<unset>}"
  echo "vllm_cache_root=$VLLM_CACHE_ROOT"
  echo "torchinductor_cache_dir=$TORCHINDUCTOR_CACHE_DIR"
  echo "vllm_bin=$VLLM_BIN"
  echo "vllm_version=$VLLM_VERSION_TEXT"
  echo "vllm_source_path=$VLLM_SOURCE_PATH"
  echo "vllm_use_v1=1"
  echo "vllm_target_device=xpu"
  echo "oneapi_device_selector=$ONEAPI_DEVICE_SELECTOR_VALUE"
  echo "ze_affinity_mask=$GPU_INDEX"
  echo "prefix_caching=disabled"
  echo "language_model_only=true"
  echo "generation_config=vllm"
  echo "--- server ---"
} > "$SERVER_LOG"

HF_HOME="${HF_HOME:-/mnt/fast-ai/llm-cache/hf}" \
TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-/mnt/fast-ai/llm-cache/hf/transformers}" \
VLLM_CACHE_ROOT="$VLLM_CACHE_ROOT" \
TORCHINDUCTOR_CACHE_DIR="$TORCHINDUCTOR_CACHE_DIR" \
VLLM_NO_USAGE_STATS=1 \
HF_HUB_DISABLE_XET=1 \
VLLM_USE_V1=1 \
VLLM_TARGET_DEVICE=xpu \
ONEAPI_DEVICE_SELECTOR="$ONEAPI_DEVICE_SELECTOR_VALUE" \
ZE_AFFINITY_MASK="$GPU_INDEX" \
XPU_GRAPH="$XPU_GRAPH" \
VLLM_XPU_ENABLE_XPU_GRAPH="$VLLM_XPU_ENABLE_XPU_GRAPH" \
VLLM_XPU_FORCE_GRAPH_WITH_COMM="$VLLM_XPU_FORCE_GRAPH_WITH_COMM" \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE="$VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE" \
LD_LIBRARY_PATH="/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
"$VLLM_BIN" "${vllm_args[@]}" >> "$SERVER_LOG" 2>&1 &
server_pid="$!"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "$BASE_URL/v1/models" > "$RUN_DIR/models.json" 2> /dev/null; do
  if (( SECONDS >= deadline )); then
    echo "[gemma4-vllm] server did not become ready after ${READINESS_TIMEOUT_S}s" >&2
    tail -120 "$SERVER_LOG" >&2 || true
    exit 1
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "[gemma4-vllm] server exited before readiness" >&2
    tail -120 "$SERVER_LOG" >&2 || true
    exit 1
  fi
  sleep 5
done

echo "[gemma4-vllm] server ready"

"$PYTHON" scripts/gemma4-text-canary.py \
  --base-url "$BASE_URL" \
  --model "$MODEL_ALIAS" \
  --api-mode chat \
  --repeats "$CANARY_REPEATS" \
  --out "$RUN_DIR/chat-canary.json"

"$PYTHON" scripts/bench-openai-single-decode.py \
  --base-url "$BASE_URL" \
  --model "$MODEL_ALIAS" \
  --api-mode chat \
  --prompt-tokens "$PROMPT_TOKENS" \
  --prompt-mode "$BENCH_PROMPT_MODE" \
  --max-tokens "$MAX_TOKENS" \
  --repeats "$BENCH_REPEATS" \
  --out "$RUN_DIR/p${PROMPT_TOKENS}o${MAX_TOKENS}.json"

"$PYTHON" - "$RUN_DIR" "$LABEL" "$SERVER_LOG" "$SUMMARY_OUT" "$MODEL" <<'PY'
import json
import os
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
label = sys.argv[2]
server_log = sys.argv[3]
summary_out = Path(sys.argv[4])
model = Path(sys.argv[5])
canary = json.loads((run_dir / "chat-canary.json").read_text())
bench = json.loads(next(run_dir.glob("p*o*.json")).read_text())

server_env = {}
try:
    for line in Path(server_log).read_text(errors="replace").splitlines():
        if line == "--- server ---":
            break
        if "=" in line:
            key, value = line.split("=", 1)
            server_env[key] = value
except OSError:
    pass

def env_or_log(key: str) -> str | None:
    return os.environ.get(key) or server_env.get(key.lower()) or server_env.get(key)

def cached_tokens(row: dict) -> int | None:
    usage = row.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    value = details.get("cached_tokens")
    return value if isinstance(value, int) else None

bench_rows = bench.get("rows") or []
first_row = bench_rows[0] if bench_rows else {}
all_cached = [cached_tokens(row) for row in bench_rows]
known_cached = [value for value in all_cached if value is not None]
model_shards = sorted(model.glob("model-*.safetensors"))

out = {
    "label": label,
    "server_log": server_log,
    "run_dir": str(run_dir),
    "model_path": str(model),
    "model_file_bytes": sum(
        p.stat().st_size for p in model_shards
    ) if model.exists() else None,
    "model_shard_count": len(model_shards),
    "launcher_identity": {
        "runtime": "vllm",
        "gpu_index": env_or_log("GPU_INDEX"),
        "port": env_or_log("PORT"),
        "model_alias": env_or_log("MODEL_ALIAS"),
        "dtype": env_or_log("DTYPE"),
        "quantization": env_or_log("QUANTIZATION"),
        "max_model_len": env_or_log("MAX_MODEL_LEN"),
        "max_num_batched_tokens": env_or_log("MAX_NUM_BATCHED_TOKENS"),
        "max_num_seqs": env_or_log("MAX_NUM_SEQS"),
        "gpu_memory_utilization": env_or_log("GPU_MEMORY_UTILIZATION"),
        "kv_cache_dtype": env_or_log("KV_CACHE_DTYPE"),
        "xpu_graph": env_or_log("XPU_GRAPH"),
        "vllm_xpu_enable_xpu_graph": env_or_log("VLLM_XPU_ENABLE_XPU_GRAPH"),
        "vllm_xpu_force_graph_with_comm": env_or_log("VLLM_XPU_FORCE_GRAPH_WITH_COMM"),
        "vllm_xpu_graph_noop_comm_capture": env_or_log("VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE"),
        "compilation_config": env_or_log("COMPILATION_CONFIG"),
        "vllm_extra_args": env_or_log("VLLM_EXTRA_ARGS"),
        "vllm_cache_root": env_or_log("VLLM_CACHE_ROOT"),
        "torchinductor_cache_dir": env_or_log("TORCHINDUCTOR_CACHE_DIR"),
        "vllm_bin": env_or_log("VLLM_BIN"),
        "vllm_version": env_or_log("VLLM_VERSION"),
        "vllm_source_path": env_or_log("VLLM_SOURCE_PATH"),
        "vllm_use_v1": env_or_log("VLLM_USE_V1"),
        "vllm_target_device": env_or_log("VLLM_TARGET_DEVICE"),
        "oneapi_device_selector": env_or_log("ONEAPI_DEVICE_SELECTOR"),
        "ze_affinity_mask": env_or_log("ZE_AFFINITY_MASK"),
        "prefix_caching": env_or_log("PREFIX_CACHING"),
        "language_model_only": env_or_log("LANGUAGE_MODEL_ONLY"),
        "generation_config": env_or_log("GENERATION_CONFIG"),
    },
    "fresh_response_validity": {
        "prefix_caching": "disabled",
        "draft_history": "none",
        "benchmark_repeats_mixed": True,
        "cached_tokens_reported": bool(known_cached),
        "cached_tokens_all_zero": (
            all(value == 0 for value in known_cached) if known_cached else None
        ),
        "first_request_cached_tokens": cached_tokens(first_row),
        "first_request_tok_s_after_ttft": first_row.get("tok_s_after_ttft"),
        "first_request_tok_s_wall": first_row.get("tok_s_wall"),
        "first_request_ttft_s": first_row.get("ttft_s"),
        "first_request_prompt_tokens": first_row.get("prompt_tokens"),
        "first_request_completion_tokens": first_row.get("completion_tokens"),
        "first_request_usage": first_row.get("usage"),
    },
    "canary_pass_all": canary["summary"]["pass_all"],
    "canary_rows_completed": canary["summary"]["rows_completed"],
    "bench_summary": bench["summary"],
    "bench_run_identity": bench["run_identity"],
}
summary_out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

echo "[gemma4-vllm] summary=$SUMMARY_OUT"
