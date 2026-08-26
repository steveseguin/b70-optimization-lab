#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

export PARALLEL_SLOTS="${PARALLEL_SLOTS:-8}"
export CTX_SIZE="${CTX_SIZE:-4096}"
export THREADS="${THREADS:-8}"
export UBATCH_SIZE="${UBATCH_SIZE:-256}"
export THROUGHPUT_MODE=1

exec "${script_dir}/run-server.sh"
