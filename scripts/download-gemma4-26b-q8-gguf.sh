#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
REPO_ID="${REPO_ID:-unsloth/gemma-4-26B-A4B-it-GGUF}"
REVISION="${REVISION:-3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a}"
FILENAME="${FILENAME:-gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf}"
DEST_DIR="${DEST_DIR:-/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf}"
HF_TOKEN_FILE="${HF_TOKEN_FILE:-/home/steve/.config/huggingface/token}"
CURL_AUTH_CONFIG="${CURL_AUTH_CONFIG:-/home/steve/.config/huggingface/curl-auth.conf}"
CURL_RETRIES="${CURL_RETRIES:-20}"
EXPECTED_BYTES="${EXPECTED_BYTES:-}"
MIN_BYTES="${MIN_BYTES:-}"

if [[ -z "$EXPECTED_BYTES" \
  && "$REPO_ID" == "unsloth/gemma-4-26B-A4B-it-GGUF" \
  && "$FILENAME" == "gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf" ]]; then
  EXPECTED_BYTES="27636230944"
fi
if [[ -z "$MIN_BYTES" \
  && "$REPO_ID" == "unsloth/gemma-4-26B-A4B-it-GGUF" \
  && "$FILENAME" == "gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf" ]]; then
  MIN_BYTES="25000000000"
fi
MIN_BYTES="${MIN_BYTES:-0}"

mkdir -p "$DEST_DIR"

if [[ -z "${HF_TOKEN:-}" && -r "$HF_TOKEN_FILE" ]]; then
  export HF_TOKEN
  HF_TOKEN="$(tr -d '\r\n' < "$HF_TOKEN_FILE")"
fi

export REPO_ID REVISION FILENAME DEST_DIR EXPECTED_BYTES MIN_BYTES
OUT="$DEST_DIR/$FILENAME"
PART="$OUT.part"
META="$OUT.metadata.json"
URL="${HF_URL:-https://huggingface.co/${REPO_ID}/resolve/${REVISION}/${FILENAME}?download=true}"

file_size() {
  stat -c '%s' "$1"
}

write_metadata() {
  local size_bytes
  size_bytes="$(file_size "$OUT")"
  cat > "$META" <<EOF
{
  "repo_id": "$REPO_ID",
  "revision": "$REVISION",
  "filename": "$FILENAME",
  "path": "$OUT",
  "size_bytes": $size_bytes,
  "downloaded_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
}

if [[ -s "$OUT" ]]; then
  size_bytes="$(file_size "$OUT")"
  if [[ -n "$EXPECTED_BYTES" ]] && (( size_bytes != EXPECTED_BYTES )); then
    echo "Existing file size does not match pinned $FILENAME: ${size_bytes} bytes != ${EXPECTED_BYTES}" >&2
    echo "Move or remove it before retrying." >&2
    exit 1
  fi
  if (( size_bytes < MIN_BYTES )); then
    echo "Existing file is too small for $FILENAME: ${size_bytes} bytes < ${MIN_BYTES}" >&2
    echo "Move or remove it before retrying." >&2
    exit 1
  fi
  [[ -s "$META" ]] || write_metadata
  echo "$OUT"
  exit 0
fi

tmp_auth_config=""
cleanup() {
  if [[ -n "$tmp_auth_config" ]]; then
    rm -f "$tmp_auth_config"
  fi
}
trap cleanup EXIT

curl_args=(
  --location
  --fail
  --continue-at -
  --retry "$CURL_RETRIES"
  --retry-all-errors
  --connect-timeout 30
  --speed-time 120
  --speed-limit 1024
  --output "$PART"
)

if [[ -r "$CURL_AUTH_CONFIG" ]]; then
  curl_args+=(--config "$CURL_AUTH_CONFIG")
elif [[ -n "${HF_TOKEN:-}" ]]; then
  tmp_auth_config="$(mktemp)"
  chmod 600 "$tmp_auth_config"
  printf 'header = "Authorization: Bearer %s"\n' "$HF_TOKEN" > "$tmp_auth_config"
  curl_args+=(--config "$tmp_auth_config")
fi

if command -v curl >/dev/null 2>&1; then
  if curl "${curl_args[@]}" "$URL"; then
    mv "$PART" "$OUT"
    size_bytes="$(file_size "$OUT")"
    if [[ -n "$EXPECTED_BYTES" ]] && (( size_bytes != EXPECTED_BYTES )); then
      echo "Downloaded file size does not match pinned $FILENAME: ${size_bytes} bytes != ${EXPECTED_BYTES}" >&2
      exit 1
    fi
    if (( size_bytes < MIN_BYTES )); then
      echo "Downloaded file is too small for $FILENAME: ${size_bytes} bytes < ${MIN_BYTES}" >&2
      exit 1
    fi
    write_metadata
    echo "$OUT"
    exit 0
  fi
  echo "curl download failed; falling back to huggingface_hub" >&2
fi

"$PYTHON" - <<'PY'
import os
import json
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import hf_hub_download

repo_id = os.environ["REPO_ID"]
revision = os.environ["REVISION"]
filename = os.environ["FILENAME"]
dest_dir = Path(os.environ["DEST_DIR"]).expanduser()
expected_bytes = int(os.environ.get("EXPECTED_BYTES") or "0")
min_bytes = int(os.environ.get("MIN_BYTES") or "0")

path = hf_hub_download(
    repo_id=repo_id,
    filename=filename,
    revision=revision,
    local_dir=dest_dir,
)
size_bytes = Path(path).stat().st_size
if expected_bytes and size_bytes != expected_bytes:
    raise SystemExit(
        f"Downloaded file size does not match pinned {filename}: "
        f"{size_bytes} bytes != {expected_bytes}"
    )
if min_bytes and size_bytes < min_bytes:
    raise SystemExit(
        f"Downloaded file is too small for {filename}: "
        f"{size_bytes} bytes < {min_bytes}"
    )
metadata_path = Path(str(path) + ".metadata.json")
metadata_path.write_text(
    json.dumps(
        {
            "repo_id": repo_id,
            "revision": revision,
            "filename": filename,
            "path": str(path),
            "size_bytes": size_bytes,
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        indent=2,
        sort_keys=True,
    )
    + "\n"
)
print(path)
PY
