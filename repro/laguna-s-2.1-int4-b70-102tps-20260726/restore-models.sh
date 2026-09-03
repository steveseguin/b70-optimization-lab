#!/usr/bin/env bash
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly manifest="$script_dir/manifests/model-release-files.sha256"
readonly default_root="${REPRO_MODEL_ROOT:-/mnt/fast-ai/llm-models/laguna-s-2.1}"

die() {
  printf 'Laguna model restore: %s\n' "$*" >&2
  exit 2
}

verify_models() {
  local root="$1" scratch
  [[ -d "$root/int4" && -d "$root/dflash-int4" ]] \
    || die "target/draft folders are missing below $root"
  scratch="$(mktemp -d)"
  trap 'rm -rf -- "$scratch"' RETURN
  (
    cd "$root"
    sha256sum --check --strict "$manifest"
    awk '{sub(/^[^ ]+  /, ""); print}' "$manifest" | LC_ALL=C sort \
      > "$scratch/expected.txt"
    find int4 dflash-int4 -type f \
      ! -path '*/.cache/*' \
      ! -path '*/.verification/*' \
      -printf '%p\n' | LC_ALL=C sort > "$scratch/actual.txt"
  )
  if ! cmp -- "$scratch/expected.txt" "$scratch/actual.txt" >/dev/null; then
    comm -3 "$scratch/expected.txt" "$scratch/actual.txt" >&2 || true
    die "release payload file set differs from the tracked manifest"
  fi
  printf 'model_verification=PASS\n'
  printf 'model_root=%s\n' "$root"
  printf 'release_files=32\n'
  rm -rf -- "$scratch"
  trap - RETURN
}

download_models() {
  local root="$1" python token_file token
  python="${REPRO_PYTHON:-python3}"
  command -v "$python" >/dev/null || die "Python not found: $python"
  token_file="${HF_TOKEN_FILE:-${HOME:-}/.config/huggingface/token}"
  [[ -r "$token_file" ]] || die "Hugging Face token file is unreadable: $token_file"
  IFS= read -r token < "$token_file"
  [[ -n "$token" ]] || die "Hugging Face token file is empty"
  mkdir -p -- "$root"
  HF_TOKEN="$token" "$python" - "$root" <<'PY'
import os
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

root = Path(sys.argv[1]).resolve()
jobs = (
    (
        "poolside/Laguna-S-2.1-INT4",
        "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb",
        root / "int4",
    ),
    (
        "poolside/Laguna-S-2.1-DFlash-INT4",
        "5e07c246915c86dc6920fead03d019989224f2ba",
        root / "dflash-int4",
    ),
)
for repo_id, revision, destination in jobs:
    snapshot_download(
        repo_id=repo_id,
        revision=revision,
        local_dir=destination,
        token=os.environ["HF_TOKEN"],
    )
PY
  unset token
  verify_models "$root"
}

[[ $# -ge 1 && $# -le 2 ]] \
  || die "usage: restore-models.sh --verify|--download [MODEL_ROOT]"
action="$1"
if [[ $# -lt 2 && -z "${REPRO_MODEL_ROOT:-}" && ! -d "$default_root" ]]; then
  die "MODEL_ROOT was not given and the default root is absent: $default_root (pass MODEL_ROOT or set REPRO_MODEL_ROOT)"
fi
model_root="$(realpath -m -- "${2:-$default_root}")"
case "$action" in
  --verify)
    verify_models "$model_root"
    ;;
  --download)
    download_models "$model_root"
    ;;
  *)
    die "usage: restore-models.sh --verify|--download [MODEL_ROOT]"
    ;;
esac
