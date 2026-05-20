#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/../.." && pwd)"

source "$THIS_DIR/configs/promoted-env.sh"
set -a
source "$THIS_DIR/configs/bench-89.env"
set +a

export OUTDIR="${OUTDIR:-/mnt/fast-ai/bench-results/minimax-m27-b70-89tps}"
mkdir -p "$OUTDIR"

echo "Cold or first pass. This may be low if AOT/graph caches are cold."
bash "$REPO_ROOT/scripts/bench-vllm-minimax-autoround-xpu.sh"

echo "Warm pass. Use this for the sanity comparison."
bash "$REPO_ROOT/scripts/bench-vllm-minimax-autoround-xpu.sh"

