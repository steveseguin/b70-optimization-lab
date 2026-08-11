#!/usr/bin/env bash
set -euo pipefail

# Two-replica Muse Glimmer 30B BF16 production fleet.
# Replica A: GPUs 0+1 on :19470. Replica B: GPUs 2+3 on :19471.
# Identity: lossless BF16 target, DFlash drafter n_max=5 p_min=0.1,
# single slot per replica (multi-slot DFlash collapses; see
# experiments/muse-glimmer-30b-b70/sweeps/20260810-bigwin-topology-screens.md).

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

MODEL="${MODEL:-/mnt/usb-models/muse-glimmer-30b-extra/Muse-Glimmer-30B-BF16-00001-of-00002.gguf}"
DRAFT="${DRAFT:-/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/dflash-kquant.gguf}"
MMPROJ="${MMPROJ:-/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/mmproj-Muse-Glimmer-30B-BF16.gguf}"
LLAMA_SERVER="${LLAMA_SERVER:-/home/steve/src/llama.cpp-muse-glimmer/build-sycl-b70-aot-bmg-g31/bin/llama-server}"
OUT_DIR="${OUT_DIR:-/mnt/fast-ai/bench-results/muse-glimmer-30b/servers}"
HOST="${HOST:-127.0.0.1}"
CTX_SIZE="${CTX_SIZE:-65536}"
CACHE_RAM_MIB="${CACHE_RAM_MIB:-8192}"
SPEC_N_MAX="${SPEC_N_MAX:-5}"
SPEC_P_MIN="${SPEC_P_MIN:-0.1}"

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
  local sel="$1" port="$2" name="$3"
  echo "[muse-fleet] replica $name devices=$sel port=$port"
  ONEAPI_DEVICE_SELECTOR="level_zero:$sel" "$LLAMA_SERVER" \
    -m "$MODEL" --mmproj "$MMPROJ" \
    --host "$HOST" --port "$port" \
    -ngl 99 -c "$CTX_SIZE" --parallel 1 -b 1024 -ub 1024 --threads 8 \
    -fa on --jinja --cache-ram "$CACHE_RAM_MIB" \
    --alias muse-glimmer-30b-bf16 \
    --spec-type draft-dflash --spec-draft-model "$DRAFT" \
    --spec-draft-n-max "$SPEC_N_MAX" --spec-draft-p-min "$SPEC_P_MIN" \
    --spec-draft-ngl 99 \
    > "$OUT_DIR/prod-bf16-$name-port$port-$stamp.log" 2>&1 &
  pids+=("$!")
}

launch "0,1" 19470 gpu01
launch "2,3" 19471 gpu23

# If either replica exits, stop the fleet so systemd restarts it whole.
wait -n
echo "[muse-fleet] a replica exited; stopping fleet" >&2
exit 1
