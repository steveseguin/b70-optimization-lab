#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
classifier="${script_dir}/classify-q38-runtime-conflicts.py"

[[ -x "$classifier" ]] || {
  printf 'missing runtime classifier: %s\n' "$classifier" >&2
  exit 2
}

self_starttime=$(awk '{print $22}' "/proc/$$/stat")
"$classifier" \
  --supervisor-pid "$$" \
  --supervisor-starttime "$self_starttime" \
  --supervisor-script "$0"
