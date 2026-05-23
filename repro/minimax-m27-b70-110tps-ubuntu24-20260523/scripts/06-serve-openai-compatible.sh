#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$THIS_DIR/configs/runtime-env.sh"
source "$VENV/bin/activate"
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1

if [ ! -d "$MODEL" ]; then
  echo "Model directory is missing: $MODEL" >&2
  exit 1
fi

exec vllm serve "$MODEL" \
  --host "${VLLM_HOST:-0.0.0.0}" \
  --port "${VLLM_PORT:-8000}" \
  --trust-remote-code \
  --dtype float16 \
  --tensor-parallel-size 4 \
  --distributed-executor-backend mp \
  --max-model-len 2048 \
  --max-num-batched-tokens 512 \
  --max-num-seqs 1 \
  --block-size 256 \
  --no-enable-prefix-caching \
  --compilation-config '{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}' \
  "$@"

