#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export MAX_MODEL_LEN=4352
exec "${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh" "$@"
