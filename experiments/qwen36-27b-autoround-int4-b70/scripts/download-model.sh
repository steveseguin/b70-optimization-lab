#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=../configs/qwen36-27b-autoround.env
source "$repo_dir/experiments/qwen36-27b-autoround-int4-b70/configs/qwen36-27b-autoround.env"

mkdir -p "$HF_HOME" "$repo_dir/data"

"$QWEN36_27B_AR_VENV/bin/python" - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

repo_dir = Path(__file__).resolve().parents[3]
repo = os.environ["QWEN36_27B_AR_REPO"]
revision = os.environ["QWEN36_27B_AR_REVISION"]
hf_home = Path(os.environ["HF_HOME"])
token_path = Path.home() / ".config/huggingface/token"
token = token_path.read_text().strip() if token_path.exists() else None

api = HfApi()
info = api.model_info(repo, revision=revision, files_metadata=True, token=token)
snapshot_path = snapshot_download(
    repo_id=repo,
    revision=revision,
    cache_dir=str(hf_home / "hub"),
    token=token,
    local_files_only=False,
)

files = []
total_size = 0
for sibling in info.siblings:
    size = getattr(sibling, "size", None) or 0
    total_size += size
    files.append({"path": sibling.rfilename, "size": size})

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
out = repo_dir / "data" / f"qwen36-27b-autoround-model-snapshot-{stamp}.json"
out.write_text(json.dumps({
    "repo": repo,
    "revision": revision,
    "resolved_sha": info.sha,
    "last_modified": str(info.last_modified),
    "snapshot_path": snapshot_path,
    "total_size_bytes": total_size,
    "total_size_gib": total_size / (1024 ** 3),
    "files": files,
}, indent=2, sort_keys=True) + "\n")

print(snapshot_path)
print(out)
PY
