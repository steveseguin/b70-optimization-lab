#!/usr/bin/env bash
# Start LFM2.5-24B-A2B Q8_0 on one B70 as a user unit, in a named arm, and wait until it answers.
#   serve-lfm25.sh ARM TAG        e.g. serve-lfm25.sh r0 b   (log: $OUT/servers/ARM-TAG.log, unit lfm25-srv)
# Arms (registered in notes/2026-10-14-lfm25-24b-a2b-bringup.md):
#   r0  the build's plain path: GGML_SYCL_DISABLE_OPT=1, none of the lab's LLAMA_SYCL_* gates
#   r1  the lab's generic SYCL gates (the ones the Gemma production launcher sets that are not Gemma- or MTP-specific)
set -euo pipefail
ARM=${1:?arm}; TAG=${2:?tag}
LAB=/home/steve/b70-optimization-lab
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b}
PORT=${PORT:-18110}
GPU_INDEX=${GPU_INDEX:-1}
UNIT=lfm25-srv
case $ARM in
  r0) arm=(-E GGML_SYCL_DISABLE_OPT=1) ;;
  r1) arm=(-E GGML_SYCL_DISABLE_OPT=0 -E GGML_SYCL_ENABLE_VMM=1 -E GGML_SYCL_DISABLE_GRAPH=0
           -E UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 -E UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
           -E LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1 -E LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1
           -E LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1 -E LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1
           -E LLAMA_SYCL_F16_P021_SMALL_NCOLS=1) ;;
  # x1: strict-lossless fast path (work-tree build ~/src/llama.cpp-lfm25-work/build-lfm25): reordered layouts with
  # R0's exact arithmetic (exact DMMV for plain Q8_0 matmuls, xor-butterfly sum in the reorder expert kernel)
  x1) arm=(-E GGML_SYCL_DISABLE_OPT=0 -E GGML_SYCL_PRIORITIZE_DMMV=1 -E LLAMA_SYCL_DMMV_Q8_0_REORDER_EXACT=4
           -E LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 -E LLAMA_SYCL_MMVQ_ID_XOR_REDUCE=1)
      LLAMA_SERVER=${LLAMA_SERVER:-/home/steve/src/llama.cpp-lfm25-work/build-lfm25/bin/llama-server} ;;
  *) echo "unknown arm $ARM" >&2; exit 2 ;;
esac
common=(-E GPU_INDEX=$GPU_INDEX -E PORT=$PORT
  -E MODEL=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf/LFM2.5-24B-A2B-Q8_0.gguf -E MODEL_ALIAS=lfm25-24b-a2b
  -E LLAMA_SERVER=${LLAMA_SERVER:-/home/steve/src/llama.cpp-gemma-c926-oneapi2026.1-compat/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server}
  -E CTX_SIZE=${CTX_SIZE:-32768} -E BATCH_SIZE=2048 -E UBATCH_SIZE=512 -E FLASH_ATTN=on -E REASONING=auto
  -E GGML_SYCL_DNNL_DETERMINISTIC=1 -E OUT_DIR=$OUT/servers -E LOG=$OUT/servers/$ARM-$TAG.log
  "-E" "EXTRA_LLAMA_ARGS=--parallel 1 --cache-ram 0 --ctx-checkpoints 0 --no-cache-prompt --slot-prompt-similarity 0 --fit off --metrics --no-webui ${EXTRA_ARGS:-}")
# extra per-run environment: ARM_ENV="A=1 B=2"
for kv in ${ARM_ENV:-}; do arm+=(-E "$kv"); done
mkdir -p "$OUT/servers"
if systemctl --user is-active --quiet $UNIT; then
  systemctl --user stop $UNIT
  for i in $(seq 1 30); do ss -tln | grep -q ":$PORT " || break; sleep 1; done
fi
systemctl --user reset-failed $UNIT 2>/dev/null || true
systemd-run --user --unit=$UNIT --collect -p WorkingDirectory=$LAB "${common[@]}" "${arm[@]}" \
  bash scripts/run-gemma4-26b-llamacpp-replica.sh >/dev/null 2>&1
for i in $(seq 1 120); do
  curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { echo "[$ARM-$TAG] ready after ${i}s"; exit 0; }
  systemctl --user is-active --quiet $UNIT || { echo "[$ARM-$TAG] server died:"; tail -5 "$OUT/servers/$ARM-$TAG.log"; exit 1; }
  sleep 1
done
echo "[$ARM-$TAG] not ready after 120 s"; exit 1
