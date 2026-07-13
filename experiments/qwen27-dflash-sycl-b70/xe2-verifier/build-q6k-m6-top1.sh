#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
llama_root="${LLAMA_ROOT:-/home/steve/src/llama.cpp}"
out_dir="${Q6K_TOP1_OUT:-/mnt/fast-ai/bench-results/qwen27-q6k-m6-top1}"
binary="$out_dir/q6k-m6-top1"
model="${MODEL:-/dev/shm/qwen27-b70-model-cache/20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a/Qwen3.6-27B-Q4_0.gguf}"

mkdir -p "$out_dir"
set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u

icpx -fsycl -fsycl-targets=spir64_gen -Xs "-device ${XE2_DEVICE_TARGET:-bmg-g31}" \
  -O3 -DNDEBUG -std=c++17 \
  -I"$llama_root/ggml/src" \
  "$here/q6k-m6-top1.cpp" -o "$binary"

echo "compiled=$binary"
if [[ "${COMPILE_ONLY:-0}" != 1 ]]; then
  : "${ZE_AFFINITY_MASK:?Set ZE_AFFINITY_MASK=2 for this experiment}"
  args=("$model" "${ITERS:-10}" "${SEED:-0xb70d6}")
  if [[ -n "${FIXTURE:-}" ]]; then
    args+=("$FIXTURE")
  fi
  "$binary" "${args[@]}"
fi
