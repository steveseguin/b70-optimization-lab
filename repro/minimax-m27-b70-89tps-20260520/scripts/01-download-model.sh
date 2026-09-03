#!/usr/bin/env bash
set -euo pipefail

MODEL_ID="${MODEL_ID:-Lasimeri/MiniMax-M2.7-int4-AutoRound}"
MODEL_REVISION="${MODEL_REVISION:-1afac074ecf7c3c4504c68b83d127506f8a7e5a4}"
MODEL_DIR="${MODEL:-/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround}"
# Pre-create the Hugging Face cache that configs/promoted-env.sh points at.
HF_CACHE_DIR="${HF_HOME:-/mnt/fast-ai/llm-cache/hf}"
VENV="${VENV:-$HOME/.venvs/vllm-xpu}"

if [ -z "${MODEL:-}" ] && [ ! -d "$(dirname "$MODEL_DIR")" ]; then
  echo "MODEL is unset and the default model parent does not exist: $(dirname "$MODEL_DIR") (set MODEL to the download directory)" >&2
  exit 2
fi
if [ -z "${HF_HOME:-}" ] && [ ! -d "$(dirname "$HF_CACHE_DIR")" ]; then
  echo "HF_HOME is unset and the default cache parent does not exist: $(dirname "$HF_CACHE_DIR") (set HF_HOME to the Hugging Face cache directory)" >&2
  exit 2
fi
mkdir -p "$(dirname "$MODEL_DIR")" "$HF_CACHE_DIR"

if [ ! -x "$VENV/bin/python" ]; then
  python3.12 -m venv "$VENV"
fi
source "$VENV/bin/activate"
python -m pip install -U pip huggingface_hub hf-xet

args=(huggingface-cli download "$MODEL_ID" --revision "$MODEL_REVISION" --local-dir "$MODEL_DIR")
if [ -n "${HF_TOKEN:-}" ]; then
  args+=(--token "$HF_TOKEN")
fi
"${args[@]}"

du -sh "$MODEL_DIR"
sha256sum "$MODEL_DIR"/config.json "$MODEL_DIR"/quantization_config.json \
  "$MODEL_DIR"/model.safetensors.index.json "$MODEL_DIR"/tokenizer_config.json \
  "$MODEL_DIR"/tokenizer.json
