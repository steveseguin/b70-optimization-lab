#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
REPO_ID="${REPO_ID:-unsloth/gemma-4-26B-A4B-it-GGUF}"
FILENAME="${FILENAME:-gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf}"
DEST_DIR="${DEST_DIR:-/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf}"

mkdir -p "$DEST_DIR"

export REPO_ID FILENAME DEST_DIR
"$PYTHON" - <<'PY'
import os
from pathlib import Path

from huggingface_hub import hf_hub_download

repo_id = os.environ["REPO_ID"]
filename = os.environ["FILENAME"]
dest_dir = Path(os.environ["DEST_DIR"]).expanduser()

path = hf_hub_download(
    repo_id=repo_id,
    filename=filename,
    local_dir=dest_dir,
)
print(path)
PY
