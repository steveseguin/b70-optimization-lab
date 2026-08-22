#!/usr/bin/env bash
set -euo pipefail

MODEL_ID="${MODEL_ID:-Lasimeri/MiniMax-M2.7-int4-AutoRound}"
MODEL_REVISION="${MODEL_REVISION:-1afac074ecf7c3c4504c68b83d127506f8a7e5a4}"
MODEL_DIR="${MODEL:-/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround}"
VENV="${VENV:-$HOME/.venvs/vllm-xpu}"

mkdir -p "$(dirname "$MODEL_DIR")" /mnt/fast-ai/llm-cache/hf

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
