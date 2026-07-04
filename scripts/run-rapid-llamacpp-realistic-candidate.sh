#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19600}"
MODEL="${MODEL:?MODEL must point to a GGUF file}"
MODEL_ALIAS="${MODEL_ALIAS:-rapid-llamacpp-model}"
LABEL="${LABEL:-${MODEL_ALIAS}-realistic}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/runs/${LABEL}-${STAMP}}"
OUT_DIR="${OUT_DIR:-$ROOT/data/rapid-model-snapshots-b70}"
OUT="${OUT:-$OUT_DIR/${LABEL}-${STAMP}.json}"
SUITE="${SUITE:-$ROOT/repro/rapid-model-snapshots-b70/realistic-suite-v1.json}"
MAX_TOKENS="${MAX_TOKENS:-128}"
METRIC_TOKENS="${METRIC_TOKENS:-100}"
API_MODE="${API_MODE:-chat}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
# Strict fresh-response runs must not reuse llama.cpp's per-request prompt KV
# cache. Keep this default here instead of relying on fragile shell-provided
# JSON at the call site; callers can still override REQUEST_EXTRA_JSON when
# intentionally running a diagnostic non-headline benchmark.
REQUEST_EXTRA_JSON="${REQUEST_EXTRA_JSON:-{\"cache_prompt\":false}}"
LLAMA_SRC="${LLAMA_SRC:-/home/steve/src/llama.cpp}"

mkdir -p "$RUN_DIR" "$OUT_DIR"

server_pid=""
cleanup() {
  if [[ -n "${server_pid:-}" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT"

{
  echo "date_utc=$STAMP"
  echo "gpu_index=$GPU_INDEX"
  echo "port=$PORT"
  echo "label=$LABEL"
  echo "model=$MODEL"
  echo "model_alias=$MODEL_ALIAS"
  echo "run_dir=$RUN_DIR"
  echo "out=$OUT"
  echo "suite=$SUITE"
  echo "max_tokens=$MAX_TOKENS"
  echo "metric_tokens=$METRIC_TOKENS"
  echo "ctx_size=${CTX_SIZE:-4096}"
  echo "batch_size=${BATCH_SIZE:-1024}"
  echo "ubatch_size=${UBATCH_SIZE:-256}"
  echo "n_parallel=${N_PARALLEL:-1}"
  echo "flash_attn=${FLASH_ATTN:-on}"
  echo "cache_type_k=${CACHE_TYPE_K:-f16}"
  echo "cache_type_v=${CACHE_TYPE_V:-f16}"
  echo "llama_server=${LLAMA_SERVER:-/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server}"
  echo "llama_src=$LLAMA_SRC"
  if git -C "$LLAMA_SRC" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "llama_git_commit=$(git -C "$LLAMA_SRC" rev-parse HEAD)"
    echo "llama_git_short_commit=$(git -C "$LLAMA_SRC" rev-parse --short HEAD)"
    if [[ -n "$(git -C "$LLAMA_SRC" status --short)" ]]; then
      echo "llama_git_dirty=1"
    else
      echo "llama_git_dirty=0"
    fi
  else
    echo "llama_git_commit=<not-a-git-worktree>"
    echo "llama_git_dirty=<unknown>"
  fi
  echo "extra_llama_args=${EXTRA_LLAMA_ARGS:-}"
  echo "request_extra_json=$REQUEST_EXTRA_JSON"
} > "$RUN_DIR/identity.env"

if git -C "$LLAMA_SRC" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$LLAMA_SRC" status --short > "$RUN_DIR/llama-status.txt"
  git -C "$LLAMA_SRC" diff --binary > "$RUN_DIR/llama.patch"
fi

GPU_INDEX="$GPU_INDEX" PORT="$PORT" MODEL="$MODEL" MODEL_ALIAS="$MODEL_ALIAS" \
  scripts/serve-rapid-llamacpp-model.sh \
  > "$RUN_DIR/server.stdout.log" 2>&1 &
server_pid=$!
echo "$server_pid" > "$RUN_DIR/server.pid"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "server exited before readiness; see $RUN_DIR/server.stdout.log" >&2
    tail -80 "$RUN_DIR/server.stdout.log" >&2 || true
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "timed out waiting for http://127.0.0.1:${PORT}/v1/models" >&2
    tail -80 "$RUN_DIR/server.stdout.log" >&2 || true
    exit 1
  fi
  sleep 2
done

python3 scripts/bench-openai-realistic-suite.py \
  --base-url "http://127.0.0.1:${PORT}" \
  --model "$MODEL_ALIAS" \
  --api-mode "$API_MODE" \
  --suite "$SUITE" \
  --max-tokens "$MAX_TOKENS" \
  --metric-tokens "$METRIC_TOKENS" \
  --request-extra-json "$REQUEST_EXTRA_JSON" \
  --out "$OUT" \
  > "$RUN_DIR/bench.stdout.log" 2>&1

cp "$OUT" "$RUN_DIR/result.json"

python3 - "$OUT" <<'PY'
import json
import sys
path = sys.argv[1]
with open(path) as f:
    result = json.load(f)
gate = result.get("realistic_final_gate", {})
summary = result.get("summary", {}).get("tok_s_1_100_after_ttft", {})
full = result.get("summary", {}).get("tok_s_after_ttft_full", {})
wall = result.get("summary", {}).get("tok_s_wall_full", {})
ttft = result.get("summary", {}).get("ttft_ms", {})
print(json.dumps({
    "path": path,
    "passed": gate.get("passed"),
    "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
    "median_tok_s_1_100_after_ttft": summary.get("median"),
    "p10_tok_s_1_100_after_ttft": summary.get("p10"),
    "mean_tok_s_1_100_after_ttft": summary.get("mean"),
    "median_tok_s_after_ttft_full": full.get("median"),
    "median_wall_tok_s_full": wall.get("median"),
    "median_ttft_ms": ttft.get("median"),
}, indent=2))
PY

echo "$OUT"
