#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GPU_INDEX="${GPU_INDEX:-1}"
PORT="${PORT:-19431}"
LABEL="${LABEL:-llamacpp-mtp3-aot-np1-realistic128}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/${LABEL}-${STAMP}}"
OUT_DIR="${OUT_DIR:-$ROOT/data/qwen36-27b-mtp-gguf-q4-b70-baselines}"
OUT="${OUT:-$OUT_DIR/${LABEL}-${STAMP}.json}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-240}"

mkdir -p "$RUN_DIR" "$OUT_DIR"

server_pid=""
cleanup() {
  if [[ -n "${server_pid:-}" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

cd "$ROOT"

{
  echo "date_utc=$STAMP"
  echo "gpu_index=$GPU_INDEX"
  echo "port=$PORT"
  echo "label=$LABEL"
  echo "run_dir=$RUN_DIR"
  echo "out=$OUT"
  echo "enable_mtp=${ENABLE_MTP:-1}"
  echo "mtp_n_max=${MTP_N_MAX:-3}"
  echo "mtp_n_min=${MTP_N_MIN:-0}"
  echo "mtp_p_min=${MTP_P_MIN:-0.00}"
  echo "ctx_size=${CTX_SIZE:-4096}"
  echo "batch_size=${BATCH_SIZE:-1024}"
  echo "ubatch_size=${UBATCH_SIZE:-256}"
  echo "n_parallel=${N_PARALLEL:-1}"
  echo "flash_attn=${FLASH_ATTN:-on}"
  echo "cache_type_k=${CACHE_TYPE_K:-f16}"
  echo "cache_type_v=${CACHE_TYPE_V:-f16}"
  echo "extra_llama_args=${EXTRA_LLAMA_ARGS:-}"
} > "$RUN_DIR/identity.env"

GPU_INDEX="$GPU_INDEX" PORT="$PORT" \
  scripts/serve-qwen36-27b-mtp-gguf-llamacpp.sh \
  > "$RUN_DIR/server.stdout.log" 2>&1 &
server_pid=$!
echo "$server_pid" > "$RUN_DIR/server.pid"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "server exited before readiness; see $RUN_DIR/server.stdout.log" >&2
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "timed out waiting for http://127.0.0.1:${PORT}/v1/models" >&2
    exit 1
  fi
  sleep 2
done

BASE_URL="http://127.0.0.1:${PORT}" \
MODEL="${MODEL:-qwen36-27b-mtp-gguf-q4}" \
LABEL="$LABEL" \
OUT="$OUT" \
REQUEST_EXTRA_JSON="${REQUEST_EXTRA_JSON:-{}}" \
  scripts/bench-qwen36-27b-mtp-gguf-realistic.sh \
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
ttft = result.get("summary", {}).get("ttft_ms", {})
print(json.dumps({
    "path": path,
    "passed": gate.get("passed"),
    "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
    "median_tok_s_1_100_after_ttft": summary.get("median"),
    "p10_tok_s_1_100_after_ttft": summary.get("p10"),
    "mean_tok_s_1_100_after_ttft": summary.get("mean"),
    "median_ttft_ms": ttft.get("median"),
}, indent=2))
PY
echo "$OUT"
