#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
source "$ROOT/configs/reap.env"
set +a

workers="${HF_DOWNLOAD_WORKERS:-4}"
attempts="${HF_DOWNLOAD_ATTEMPTS:-0}"
attempt=1

mkdir -p "$MODEL" "$HF_HOME"

args=(download "$REAP_MINIMAX_REPO" --local-dir "$MODEL" --max-workers "$workers")
if [ -n "${HF_TOKEN:-}" ]; then
  args+=(--token "$HF_TOKEN")
fi

while true; do
  echo "hf download attempt $attempt: $REAP_MINIMAX_REPO -> $MODEL (workers=$workers)"
  if "$VENV/bin/hf" "${args[@]}"; then
    break
  fi

  if [ "$attempts" != "0" ] && [ "$attempt" -ge "$attempts" ]; then
    echo "hf download failed after $attempt attempts" >&2
    exit 1
  fi

  attempt=$((attempt + 1))
  sleep 10
done

find "$MODEL" -maxdepth 1 -type f -printf '%f\n' | sort | sed -n '1,80p'
