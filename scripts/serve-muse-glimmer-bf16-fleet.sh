#!/usr/bin/env bash
set -euo pipefail

# Two-replica Muse Glimmer 30B BF16 production fleet (asymmetric, 2026-08-11).
# Replica A (:19470, GPUs 0+1): TEXT lane - tensor parallel (-sm tensor),
#   BF16 DFlash drafter n_max=15 p_min=0.15, no mmproj, ub 1024.
#   TP2 measured 56.2 json / 49.1 code / 31.9 prose (2026-08-11).
# Replica B (:19471, GPUs 2+3): VISION lane - kquant drafter n_max=6 p_min=0.1
#   plus BF16 mmproj, ub 1024 (proven 32.07 GB fit).
# Single slot per replica (multi-slot DFlash collapses). Frontdoor routes
# image requests to replica B via FRONTDOOR_VISION_BACKEND_INDICES=1. See
# experiments/muse-glimmer-30b-b70/sweeps/ for the evidence chain.

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

MODEL="${MODEL:-/mnt/usb-models/muse-glimmer-30b-extra/Muse-Glimmer-30B-BF16-00001-of-00002.gguf}"
DRAFT_KQUANT="${DRAFT_KQUANT:-/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/dflash-kquant.gguf}"
DRAFT_BF16="${DRAFT_BF16:-/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/dflash-bf16.gguf}"
MMPROJ="${MMPROJ:-/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/mmproj-Muse-Glimmer-30B-BF16.gguf}"
LLAMA_SERVER="${LLAMA_SERVER:-/home/steve/src/llama.cpp-muse-100/build-sycl-b70-aot-bmg-g31/bin/llama-server}"
OUT_DIR="${OUT_DIR:-/mnt/fast-ai/bench-results/muse-glimmer-30b/servers}"
HOST="${HOST:-127.0.0.1}"
CTX_SIZE="${CTX_SIZE:-65536}"
CACHE_RAM_MIB="${CACHE_RAM_MIB:-8192}"

echo "[muse-fleet] sourcing oneAPI environment"
set +eu
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
setvars_rc=$?
set -eu
if ! "$LLAMA_SERVER" --version >/dev/null 2>&1; then
  echo "[muse-fleet] llama-server not runnable after setvars (rc=$setvars_rc)" >&2
  exit 1
fi
echo "[muse-fleet] runtime ok (setvars rc=$setvars_rc)"
export UR_L0_USE_IMMEDIATE_COMMANDLISTS="${UR_L0_USE_IMMEDIATE_COMMANDLISTS:-1}"
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS="${UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS:-1}"
export GGML_SYCL_ENABLE_VMM="${GGML_SYCL_ENABLE_VMM:-1}"

mkdir -p "$OUT_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

pids=()
cleanup() {
  trap - INT TERM EXIT
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

launch() {
  local sel="$1" port="$2" name="$3" ub="$4" draft="$5" nmax="$6" pmin="$7"
  shift 7
  echo "[muse-fleet] replica $name devices=$sel port=$port ub=$ub nmax=$nmax"
  ONEAPI_DEVICE_SELECTOR="level_zero:$sel" "$LLAMA_SERVER" \
    -m "$MODEL" \
    --host "$HOST" --port "$port" \
    -ngl 99 -c "$CTX_SIZE" --parallel 1 -b "$ub" -ub "$ub" --threads 8 \
    -fa on --jinja --cache-ram "$CACHE_RAM_MIB" \
    --alias muse-glimmer-30b-bf16 \
    --spec-type draft-dflash --spec-draft-model "$draft" \
    --spec-draft-n-max "$nmax" --spec-draft-p-min "$pmin" \
    --spec-draft-ngl 99 \
    "$@" \
    > "$OUT_DIR/prod-bf16-$name-port$port-$stamp.log" 2>&1 &
  pids+=("$!")
}

# text lane: tensor-parallel pair, BF16 drafter, deep blocks
launch "0,1" 19470 gpu01-text 1024 "$DRAFT_BF16" 15 0.15 -sm tensor
# vision lane: kquant drafter + mmproj, proven memory fit
launch "2,3" 19471 gpu23-vision 1024 "$DRAFT_KQUANT" 6 0.1 --mmproj "$MMPROJ"

# If either replica exits, stop the fleet so systemd restarts it whole.
wait -n
echo "[muse-fleet] a replica exited; stopping fleet" >&2
exit 1
