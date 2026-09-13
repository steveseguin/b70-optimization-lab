#!/usr/bin/env bash
# Rebase onto vLLM v0.29.0: the FP8 27B lane (R187 profile: whole-graph piecewise compile, XPU graph off, GDN split-mixed,
# block W8A16, MTP depth 1) strict pair on the R304 candidate, TP2. The FP8 lane's kernel needs are oneDNN r137a + r137b,
# both in R304's library. Published R187: MTP1 54.935 tok/s, MTP0 33.097. Queued behind the R304 INT4 work.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts; R=/home/steve/b70-optimization-lab/repro
wrap=$out/qwen38-fp8-rebase-v0290-20260913-wrapper.log
log() { printf '[fp8-rebase %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "$wrap"; }
until [[ -e /mnt/fast-ai/bench-results/rebase-v0290-20260912/r304-all-DONE ]]; do sleep 30; done
IMAGE=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304}; IMAGE_ID=$(docker image inspect "$IMAGE" --format '{{.Id}}')
export EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
CC='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-|upstream-'; do sleep 30; done; sleep 20; }
root=$out/qwen38-fp8-rebase-v0290-${RB:-rb1}-20260913
[[ -e "$root/campaign.log" ]] && { log "root used"; exit 0; }
wait_free; log "starting -> $root ($IMAGE)"
env XPU_EXTENSION_SHA256_OVERRIDE=bbce7295fb8a58bad456675cfac7cdf3d1e29fe7a9dd5c0970741b130616c932 XPU_OPS_SHA256_OVERRIDE=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3 \
  LAYERNORM_SHA256_OVERRIDE=3f949e537ccc52744d7eba52ed2034b20ee3fbaeaabbfab4e672f1dc9767602c VLLM_XPU_DRAFT_LM_HEAD_INT4=1 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 XPU_GRAPH=0 \
  COMPILATION_CONFIG="$CC" IMAGE_OVERRIDE=$IMAGE IMAGE_ID_OVERRIDE=$IMAGE_ID ROOT=$root bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh >>"$wrap" 2>&1
log "engine exit $?"; grep -E 'G[123] |median_tok_s' "$wrap" | tail -6 | sed 's/^/    /'
log "=== FP8 rebase strict complete ==="; echo done > $out/qwen38-fp8-rebase-v0290-20260913-DONE
