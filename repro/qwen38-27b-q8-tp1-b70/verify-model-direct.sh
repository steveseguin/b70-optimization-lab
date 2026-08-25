#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
model_dir="${1:-${MODEL_DIR:-}}"
[[ -n "${model_dir}" ]] || {
    printf 'Usage: MODEL_DIR=/path/to/model-directory %s\n' "$0" >&2
    exit 3
}
if (( $# > 0 )); then shift; fi
exec "${repo_root}/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
    "${script_dir}/model-direct.json" "${model_dir}" "$@"
