#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${PROFILE:-mtp3}"
GPU_INDEX="${GPU_INDEX:-2}"
PORT="${PORT:-19432}"
MODE="${MODE:-normal}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/cycle-timeline/${PROFILE}-${MODE}-gpu${GPU_INDEX}-${STAMP}}"
OUT_DIR="${OUT_DIR:-$ROOT/data/qwen27-cycle-timeline/${PROFILE}-${MODE}-${STAMP}}"

if [[ "$MODE" != "normal" && "$MODE" != "sycl-trace" ]]; then
  echo "MODE must be normal or sycl-trace" >&2
  exit 2
fi
if [[ "${CONFIRM_GPU_USE:-0}" != "1" ]]; then
  echo "Refusing GPU use without CONFIRM_GPU_USE=1; GPU_INDEX=$GPU_INDEX MODE=$MODE" >&2
  exit 3
fi

mkdir -p "$RUN_DIR" "$OUT_DIR"
RESULT="$OUT_DIR/result.json"

if [[ "$MODE" == "normal" ]]; then
  GPU_INDEX="$GPU_INDEX" PORT="$PORT" SPEC_PROFILE="$PROFILE" \
  PROFILES="$PROFILE" OUT_DIR="$OUT_DIR" RUN_ROOT="$RUN_DIR" \
    "$ROOT/scripts/run-qwen27-tp1-phase0-baselines.sh"
  result_file="$(find "$OUT_DIR" -maxdepth 1 -name '*.json' -print -quit)"
  run_log="$(find "$RUN_DIR" -name server.stdout.log -print -quit)"
else
  echo "sycl-trace mode is intentionally not automated through the strict suite." >&2
  echo "Run the server under sycl-trace for one short diagnostic request, then call the parser:" >&2
  echo "/opt/intel/oneapi/compiler/2026.0/bin/sycl-trace --ur.call --level_zero --print-format=compact scripts/serve-qwen36-27b-mtp-gguf-llamacpp.sh" >&2
  exit 4
fi

python3 "$ROOT/scripts/summarize-qwen27-cycle-timeline.py" \
  --result "$result_file" --server-log "$run_log" \
  --out "$OUT_DIR/timeline-summary.json" \
  --requests-out "$OUT_DIR/request-timeline.jsonl"

echo "$OUT_DIR/timeline-summary.json"
