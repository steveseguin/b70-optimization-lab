#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/configs/deepseek-v4-flash-autoround.env"

if [ ! -d "$DEEPSEEK_V4_AR_VENV" ]; then
  echo "Missing venv: $DEEPSEEK_V4_AR_VENV" >&2
  exit 1
fi

mkdir -p "$DEEPSEEK_V4_AR_MODEL_DIR" "$HF_HOME"
source "$DEEPSEEK_V4_AR_VENV/bin/activate"

python - <<'PY'
from huggingface_hub import snapshot_download
import os

repo = os.environ["DEEPSEEK_V4_AR_REPO"]
revision = os.environ["DEEPSEEK_V4_AR_REVISION"]
local_dir = os.environ["DEEPSEEK_V4_AR_MODEL_DIR"]

print(f"repo={repo}")
print(f"revision={revision}")
print(f"local_dir={local_dir}")

snapshot_download(
    repo_id=repo,
    revision=revision,
    local_dir=local_dir,
    local_dir_use_symlinks=False,
    resume_download=True,
)
PY

echo "model_dir=$DEEPSEEK_V4_AR_MODEL_DIR"
