#!/usr/bin/env bash
# Qwen3.8-27B AutoRound INT4, fixed-K batch-invariant profile (2026-09-05): launch one vLLM server through the FP8 lane's
# contract-checked launcher with the INT4 identity. Depth via MTP_DEPTH (0 = no speculation; default 4).
#   MODEL_DIR   the gptq-relabelled model directory (built by the relabel builder in this scripts directory); default below
#   DRAFT_SHORTLIST  container path of the draft head's token shortlist (default the 67k list; empty = all rows; R294)
#   CLASSPAD    0 (default, the published single-user configuration) or 1 (class-consistent FP16 linears for many users; R293)
#   IMAGE / EXPECTED_IMAGE_ID  the R293 image (R276 + classpad; ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:40d46730...; R276 521eb277..., R256 f7696bca... and
#                             R228 aaf920b0... run the same code but cannot capture verify batches above 16 sequences: use XPU_GRAPH_SIZES=8 with them)
#   PORT, VLLM_CACHE_DIR, CONTAINER_NAME, SERVED_MODEL_NAME, TENSOR_PARALLEL_SIZE (2), XPU_DEVICE_MASK (0,1)
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo_root=$(cd -- "${script_dir}/../../.." && pwd)
fp8=${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
depth=${MTP_DEPTH:-4}
spec=""; [[ "${depth}" == 0 ]] || spec="{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":${depth}}"
# XPU_GRAPH=1 (default): capture the decode/verify step as an XPU graph (FULL_DECODE_ONLY, sizes 1-8). On two cards the
# captured verify step drops the per-op all-reduce host waits: depth 4 91.0 tok/s vs 68.2 eager (R247, lossless vs the
# eager MTP0 oracle); on one card it is neutral (+1%). XPU_GRAPH=0 restores the eager R239 configuration.
xpu_graph=${XPU_GRAPH:-1}; xpu_graph_sizes=${XPU_GRAPH_SIZES:-320}
if [[ "${xpu_graph}" == 1 && "${xpu_graph_sizes}" == 8 ]]; then
  compilation='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8],"max_cudagraph_capture_size":8,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
elif [[ "${xpu_graph}" == 1 ]]; then
  compilation='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64,80,100,120,160,200,240,320],"max_cudagraph_capture_size":320,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
else
  compilation='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
fi
# R293 (2026-09-11) = R276 + the class-consistent FP16 linear (docker/r290..r293-*.py). With CLASSPAD=0 (default) it runs
# R276's code path unchanged: every unquantized FP16 linear in <=32-row pieces, the published single-user headline.
# CLASSPAD=1 keeps each of those linears in one verified oneDNN M-class instead, so the 2.5 GB vocabulary projection is
# read once per step rather than once per 32 rows: the multi-user configuration (see the README's R295-R298 rows).
# R294 (2026-09-12): the draft-only INT4 lm_head scores a token shortlist (67,248 rows) instead of all 248,320; the target
# verifies every draft with its full FP16 head, so outputs cannot change (R299: 12/12 on every gate, 117.46/117.59 tok/s
# against 112.90/113.00). DRAFT_SHORTLIST= (empty) scores every row. The image is R294b = R293 + the shortlisted head.
export IMAGE=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-draft-head-shortlist-r294b}
export EXPECTED_IMAGE_ID=${EXPECTED_IMAGE_ID:-sha256:78bd728d610995d3a05a493c21a0f8a0fdc4062baa570f1c80ade02bf374baf1}
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=${DRAFT_SHORTLIST-/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt}
export VLLM_XPU_FP16_LINEAR_CLASSPAD=${CLASSPAD:-0}
export EXPECTED_XPU_EXTENSION_SHA256=${EXPECTED_XPU_EXTENSION_SHA256:-271db0d4882124e21ac6a4d080bfeab303fbb08b9ec10e11f21d10fb0723998f}
export EXPECTED_XPU_OPS_SHA256=${EXPECTED_XPU_OPS_SHA256:-6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3}
export EXPECTED_LAYERNORM_SHA256=${EXPECTED_LAYERNORM_SHA256:-50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8}
export MODEL_DIR=${MODEL_DIR:?set MODEL_DIR to the gptq-relabelled model directory built by make-gptq-relabel.py in this directory}
export MODEL_MANIFEST=${MODEL_MANIFEST:-${script_dir}/../manifests/model-gptq-relabel-r212.json}
# DRAFT_HEAD_INT4=1 (default): the MTP draft passes use a draft-only INT4 copy of the lm_head (R257: depth 4 112.4 tok/s vs
# 91.0 with the FP16 head; acceptance 3.51 vs 3.00); the target verifier head stays FP16, so outputs are unchanged.
export QUANTIZATION=gptq VLLM_XPU_FP8_BLOCK_W8A16=0 VLLM_XPU_DRAFT_LM_HEAD_INT4=${DRAFT_HEAD_INT4:-1} VLLM_XPU_W4A16_DETERMINISM_PAD=0
# VLLM_BATCH_INVARIANT stays 0: upstream vLLM refuses to boot the GDN attention backend with it set (R260), and every
# published INT4 measurement ran with it off (the strict launchers pin 0). Batch invariance on this lane comes from the
# fixed-K W4A16 kernel, the 32-row FP16 linears, GDN spec grouping and Inductor split_reductions=false instead.
export VLLM_BATCH_INVARIANT=0 VLLM_XPU_GDN_SPLIT_MIXED=1 VLLM_XPU_GDN_SPEC_GROUP=${VLLM_XPU_GDN_SPEC_GROUP:-16}
export VLLM_XPU_GEMMA_RMSNORM_TRITON=0 VLLM_XPU_RMSNORM_TRITON=0 VLLM_XPU_ENABLE_XPU_GRAPH=${xpu_graph}
# V1 model runner pinned (2026-09-12): vLLM v0.29.0 defaults XPU to the V2 runner, whose speculator has no draft INT4 head
# (single user 128 instead of 172 tok/s on the 4B). A no-op on the 0.27.2 lineage, which defaults to V1.
export VLLM_USE_V2_MODEL_RUNNER=${VLLM_USE_V2_MODEL_RUNNER:-0}
export COMPILATION_CONFIG=${COMPILATION_CONFIG:-${compilation}}
export SPECULATIVE_CONFIG=${SPECULATIVE_CONFIG:-${spec}}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-int4-fixed-k-mtp${depth}} SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen38-int4-fixed-k-mtp${depth}}
export PORT=${PORT:-18134} MAX_NUM_BATCHED_TOKENS=${MAX_NUM_BATCHED_TOKENS:-1024} GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.95}
export CONTAINER_MEMORY=${CONTAINER_MEMORY:-12g} CONTAINER_MEMORY_SWAP=${CONTAINER_MEMORY_SWAP:-16g}
if [[ "${depth}" == 0 ]]; then
  unset SPECULATIVE_CONFIG
  exec "${fp8}/run-w8a16-mtp0-strict-server.sh"
fi
# The strict launcher pins the same process-level determinism env the published campaigns ran with (TORCHINDUCTOR_DETERMINISTIC=1,
# Inductor autotune off, PYTHONHASHSEED=0, GDN persistent scratch, packed-serial-exact Gemma RMSNorm; VLLM_XPU_FP8_BLOCK_W8A16=1 is inert on gptq).
exec "${fp8}/run-w8a16-mtp1-strict-server.sh"
