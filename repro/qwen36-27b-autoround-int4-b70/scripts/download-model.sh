#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
packet=$(cd -- "$here/.." && pwd)
manifest="$packet/manifests/model.json"
python=${PYTHON:-python3}
hf_home=${HF_HOME:-$HOME/.cache/huggingface}
model_dir=${MODEL_DIR:-}

if [[ -z "${HF_TOKEN:-}" && -f "$HOME/.config/huggingface/token" ]]; then
  export HF_TOKEN
  HF_TOKEN=$(< "$HOME/.config/huggingface/token")
fi
export HF_HOME="$hf_home"

"$python" - "$manifest" "$model_dir" <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
requested_dir = sys.argv[2]
manifest = json.loads(manifest_path.read_text())

if requested_dir:
    snapshot = Path(requested_dir).resolve()
else:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SystemExit(
            "huggingface_hub is required: python -m pip install huggingface_hub"
        ) from exc
    snapshot = Path(snapshot_download(
        repo_id=manifest["repository"],
        revision=manifest["revision"],
        token=os.environ.get("HF_TOKEN") or None,
    )).resolve()

if not snapshot.is_dir():
    raise SystemExit(f"model snapshot does not exist: {snapshot}")

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data
    ).hexdigest()

for item in manifest["lfs_files"]:
    path = snapshot / item["path"]
    if not path.is_file() or path.stat().st_size != item["bytes"]:
        raise SystemExit(f"size mismatch or missing model file: {path}")
    actual = sha256(path)
    if actual != item["sha256"]:
        raise SystemExit(f"SHA256 mismatch for {path}: {actual}")

for item in manifest["small_files"]:
    path = snapshot / item["path"]
    if not path.is_file() or path.stat().st_size != item["bytes"]:
        raise SystemExit(f"size mismatch or missing model file: {path}")
    actual = git_blob(path)
    if actual != item["git_blob"]:
        raise SystemExit(f"Git blob mismatch for {path}: {actual}")

print(snapshot)
print("model revision and all recorded file identities verified")
PY
