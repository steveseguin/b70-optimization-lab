#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$THIS_DIR/configs/runtime-env.sh"

python3.12 -m venv "$VENV"
source "$VENV/bin/activate"
python -m pip install -U pip huggingface_hub

mkdir -p "$MODEL" "$HF_HOME"
export HF_HOME
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"

echo "Downloading Lasimeri/MiniMax-M2.7-int4-AutoRound to $MODEL"
echo "HF_HUB_DISABLE_XET=$HF_HUB_DISABLE_XET"

attempt=1
while true; do
  if hf download Lasimeri/MiniMax-M2.7-int4-AutoRound \
      --local-dir "$MODEL" \
      --max-workers "${HF_DOWNLOAD_WORKERS:-4}"; then
    break
  fi
  if [ "$attempt" -ge "${HF_DOWNLOAD_RETRIES:-20}" ]; then
    echo "Download failed after $attempt attempts" >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  echo "Download attempt failed; retrying attempt $attempt..."
  sleep 15
done

echo "Downloaded model files:"
du -sh "$MODEL"
find "$MODEL" -maxdepth 1 -type f | sort

