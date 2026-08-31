#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export CAMPAIGN_ID=qwen38-prefill-projection-repair-strict-replay-20260831-d55
export CONTAINER_NAME=q38-prefill-projection-repair-d55
export PORT=18355
export PREREG_PATH="$script_dir/../notes/2026-08-31-qwen38-prefill-projection-repair-strict-d55-prereg.md"
export REFERENCE_PERFORMANCE=/mnt/fast-ai/bench-results/qwen38-prefill-projection-repair-strict-20260831-d54/performance.json
exec "$script_dir/run-20260831-qwen38-prefill-projection-repair-strict-d54.sh"
