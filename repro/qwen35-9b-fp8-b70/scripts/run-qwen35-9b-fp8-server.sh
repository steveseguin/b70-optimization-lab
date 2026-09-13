#!/usr/bin/env bash
# Qwen3.5-9B FP8-dynamic on Intel Arc Pro B70 (one card by default): public launcher for the lab's vLLM XPU stack.
# Serves RedHatAI/Qwen3.5-9B-FP8-dynamic (revision 790f0576) through the R276 image with the strict launchers of the
# Qwen3.8 FP8 recipe (process-level determinism env, image contract, model manifest verification), MTP speculation via the
# model's own MTP head (method qwen3_5_mtp) and full decode-only XPU graph capture.
#   MODEL_DIR           the downloaded model directory (required; verified against manifests/model-direct-…790f0576.json)
#   MTP_DEPTH           speculative tokens per step, default 3 (0 = no speculation)
#   TENSOR_PARALLEL_SIZE 1 (default) or 2; XPU_DEVICE_MASK selects the card(s), default 0 (TP1) / 0,1 (TP2)
#   XPU_GRAPH           1 (default, FULL_DECODE_ONLY capture sizes 1-64) or 0 (piecewise compile, XPU graph off)
#   DRAFT_HEAD_INT4     1 (default): the MTP draft passes use a draft-only INT4 copy of the 248K-row lm_head (the FP8 target verifier is
#                       unchanged, so outputs are identical); 0 keeps the FP8 head for drafts too
#   PORT / CONTAINER_NAME / SERVED_MODEL_NAME / MAX_MODEL_LEN / MAX_NUM_SEQS / MAX_NUM_BATCHED_TOKENS / VLLM_CACHE_DIR as the FP8 recipe
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo_root=$(cd -- "${script_dir}/../../.." && pwd)
fp8=${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
depth=${MTP_DEPTH:-3}
spec=""; [[ "${depth}" == 0 ]] || spec="{\"method\":\"qwen3_5_mtp\",\"num_speculative_tokens\":${depth}}"
xpu_graph=${XPU_GRAPH:-1}
if [[ "${xpu_graph}" == 1 ]]; then
  compilation='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64],"max_cudagraph_capture_size":64,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
else
  # XPU_GRAPH=0: piecewise Inductor compile with the XPU graph disabled (the lab's "graph off" configuration; the strict launcher pins enforce-eager off)
  compilation='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
fi
tp=${TENSOR_PARALLEL_SIZE:-1}
export IMAGE=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-gdn-spec-group-sync-free-r276}
export EXPECTED_IMAGE_ID=${EXPECTED_IMAGE_ID:-sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad}
export EXPECTED_XPU_EXTENSION_SHA256=${EXPECTED_XPU_EXTENSION_SHA256:-271db0d4882124e21ac6a4d080bfeab303fbb08b9ec10e11f21d10fb0723998f}
export EXPECTED_XPU_OPS_SHA256=${EXPECTED_XPU_OPS_SHA256:-6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3}
export EXPECTED_LAYERNORM_SHA256=${EXPECTED_LAYERNORM_SHA256:-50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8}
export MODEL_DIR=${MODEL_DIR:?set MODEL_DIR to the downloaded RedHatAI/Qwen3.5-9B-FP8-dynamic directory (revision 790f0576)}
export MODEL_MANIFEST=${MODEL_MANIFEST:-${script_dir}/../manifests/model-direct-redhatai-qwen35-9b-fp8-dynamic-790f0576.json}
export QUANTIZATION=compressed-tensors VLLM_XPU_FP8_BLOCK_W8A16=0 VLLM_XPU_DRAFT_LM_HEAD_INT4=${DRAFT_HEAD_INT4:-1} VLLM_XPU_W4A16_DETERMINISM_PAD=0
export VLLM_BATCH_INVARIANT=0 VLLM_XPU_GDN_SPLIT_MIXED=1 VLLM_XPU_GDN_SPEC_GROUP=${VLLM_XPU_GDN_SPEC_GROUP:-16}
export VLLM_XPU_GEMMA_RMSNORM_TRITON=0 VLLM_XPU_RMSNORM_TRITON=0 VLLM_XPU_ENABLE_XPU_GRAPH=${xpu_graph}
# V1 model runner pinned (2026-09-12): vLLM v0.29.0 defaults XPU to the V2 runner, whose speculator has no draft INT4 head
# (single user 128 instead of 172 tok/s on the 4B). A no-op on the 0.27.2 lineage, which defaults to V1.
export VLLM_USE_V2_MODEL_RUNNER=${VLLM_USE_V2_MODEL_RUNNER:-0}
export TENSOR_PARALLEL_SIZE=${tp} XPU_DEVICE_MASK=${XPU_DEVICE_MASK:-$([[ "${tp}" == 2 ]] && echo 0,1 || echo 0)}
export COMPILATION_CONFIG=${COMPILATION_CONFIG:-${compilation}} SPECULATIVE_CONFIG=${SPECULATIVE_CONFIG:-${spec}}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen35-9b-fp8-mtp${depth}} SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen35-9b-fp8-mtp${depth}}
export PORT=${PORT:-18131} MAX_MODEL_LEN=${MAX_MODEL_LEN:-8192} MAX_NUM_SEQS=${MAX_NUM_SEQS:-16} MAX_NUM_BATCHED_TOKENS=${MAX_NUM_BATCHED_TOKENS:-1024}
export GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.95} CONTAINER_MEMORY=${CONTAINER_MEMORY:-12g} CONTAINER_MEMORY_SWAP=${CONTAINER_MEMORY_SWAP:-20g}
if [[ "${depth}" == 0 ]]; then unset SPECULATIVE_CONFIG; exec "${fp8}/run-w8a16-mtp0-strict-server.sh"; fi
exec "${fp8}/run-w8a16-mtp1-strict-server.sh"
