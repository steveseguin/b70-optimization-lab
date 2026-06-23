#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-18260}"
BASE_URL="${BASE_URL:-http://127.0.0.1:${PORT}}"
MODEL_ALIAS="${MODEL_ALIAS:-gemma4-26b-a4b-q8}"
MODEL="${MODEL:-/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf}"
CTX_SIZE="${CTX_SIZE:-8192}"
BATCH_SIZE="${BATCH_SIZE:-512}"
UBATCH_SIZE="${UBATCH_SIZE:-64}"
THREADS="${THREADS:-8}"
CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
POLL="${POLL:-50}"
FLASH_ATTN="${FLASH_ATTN:-on}"
REASONING="${REASONING:-off}"
EXTRA_LLAMA_ARGS="${EXTRA_LLAMA_ARGS:-}"
CANARY_REPEATS="${CANARY_REPEATS:-32}"
BENCH_REPEATS="${BENCH_REPEATS:-8}"
PROMPT_TOKENS="${PROMPT_TOKENS:-512}"
BENCH_PROMPT_MODE="${BENCH_PROMPT_MODE:-default}"
MAX_TOKENS="${MAX_TOKENS:-512}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LABEL="${LABEL:-gemma4-26b-q8-llamacpp-gpu${GPU_INDEX}-ctx${CTX_SIZE}-${STAMP}}"
RUN_DIR="${RUN_DIR:-$ROOT/data/$LABEL}"
SERVER_OUT_DIR="${SERVER_OUT_DIR:-/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers}"
SERVER_LOG="$SERVER_OUT_DIR/${LABEL}.server.log"
SUMMARY_OUT="$RUN_DIR/summary.json"

mkdir -p "$RUN_DIR" "$SERVER_OUT_DIR"

server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT"

echo "[gemma4-baseline] label=$LABEL"
echo "[gemma4-baseline] base_url=$BASE_URL"
echo "[gemma4-baseline] model=$MODEL"
echo "[gemma4-baseline] server_log=$SERVER_LOG"

GPU_INDEX="$GPU_INDEX" \
PORT="$PORT" \
MODEL_ALIAS="$MODEL_ALIAS" \
MODEL="$MODEL" \
CTX_SIZE="$CTX_SIZE" \
BATCH_SIZE="$BATCH_SIZE" \
UBATCH_SIZE="$UBATCH_SIZE" \
THREADS="$THREADS" \
CACHE_TYPE_K="$CACHE_TYPE_K" \
CACHE_TYPE_V="$CACHE_TYPE_V" \
POLL="$POLL" \
FLASH_ATTN="$FLASH_ATTN" \
REASONING="$REASONING" \
EXTRA_LLAMA_ARGS="$EXTRA_LLAMA_ARGS" \
LOG="$SERVER_LOG" \
scripts/run-gemma4-26b-llamacpp-replica.sh > "$RUN_DIR/server.stdout.log" 2>&1 &
server_pid="$!"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "$BASE_URL/v1/models" > "$RUN_DIR/models.json" 2> /dev/null; do
  if (( SECONDS >= deadline )); then
    echo "[gemma4-baseline] server did not become ready after ${READINESS_TIMEOUT_S}s" >&2
    tail -80 "$SERVER_LOG" >&2 || true
    exit 1
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "[gemma4-baseline] server exited before readiness" >&2
    tail -80 "$SERVER_LOG" >&2 || true
    exit 1
  fi
  sleep 5
done

echo "[gemma4-baseline] server ready"

python3 scripts/gemma4-text-canary.py \
  --base-url "$BASE_URL" \
  --model "$MODEL_ALIAS" \
  --api-mode chat \
  --repeats "$CANARY_REPEATS" \
  --out "$RUN_DIR/chat-canary.json"

python3 scripts/bench-openai-single-decode.py \
  --base-url "$BASE_URL" \
  --model "$MODEL_ALIAS" \
  --api-mode chat \
  --prompt-tokens "$PROMPT_TOKENS" \
  --prompt-mode "$BENCH_PROMPT_MODE" \
  --max-tokens "$MAX_TOKENS" \
  --repeats "$BENCH_REPEATS" \
  --out "$RUN_DIR/p${PROMPT_TOKENS}o${MAX_TOKENS}.json"

python3 - "$RUN_DIR" "$LABEL" "$SERVER_LOG" "$SUMMARY_OUT" "$MODEL" <<'PY'
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

def env_or_log(env_key, log_key=None):
    value = os.environ.get(env_key)
    if value:
        return value
    return server_env.get(log_key or env_key)

out = {
    "label": label,
    "server_log": server_log,
    "run_dir": str(run_dir),
    "model_path": str(model),
    "model_file_bytes": model.stat().st_size if model.exists() else None,
    "launcher_identity": {
        "gpu_index": os.environ.get("GPU_INDEX"),
        "port": os.environ.get("PORT"),
        "ctx_size": os.environ.get("CTX_SIZE"),
        "batch_size": os.environ.get("BATCH_SIZE"),
        "ubatch_size": os.environ.get("UBATCH_SIZE"),
        "threads": os.environ.get("THREADS"),
        "cache_type_k": os.environ.get("CACHE_TYPE_K"),
        "cache_type_v": os.environ.get("CACHE_TYPE_V"),
        "poll": os.environ.get("POLL"),
        "flash_attn": os.environ.get("FLASH_ATTN"),
        "reasoning": os.environ.get("REASONING"),
        "extra_llama_args": os.environ.get("EXTRA_LLAMA_ARGS"),
        "oneapi_device_selector": env_or_log("ONEAPI_DEVICE_SELECTOR"),
        "ggml_sycl_disable_opt": env_or_log("GGML_SYCL_DISABLE_OPT"),
        "ggml_sycl_disable_graph": env_or_log("GGML_SYCL_DISABLE_GRAPH"),
        "ggml_sycl_disable_dnn": env_or_log("GGML_SYCL_DISABLE_DNN"),
        "llama_cpp_commit": server_env.get("llama_cpp_commit"),
        "llama_server": server_env.get("llama_server"),
    },
    "canary_pass_all": canary["summary"]["pass_all"],
    "canary_rows_completed": canary["summary"]["rows_completed"],
    "bench_summary": bench["summary"],
    "bench_run_identity": bench["run_identity"],
}
summary_out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

echo "[gemma4-baseline] summary=$SUMMARY_OUT"
