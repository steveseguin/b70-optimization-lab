#!/usr/bin/env bash
# The record's server line (A189 server-command.shell.txt) with the model path
# and port as arguments. UNTESTED inside the container; see CONTAINER-STATUS.md.
set -euo pipefail
model="${1:?model directory (Qwen/Qwen3.8-Flash-Next-FP8 at bcd9f01d)}"
port="${2:-8000}"
# The record server's environment (from the frozen A189 launch source), minus host paths.
export CCL_ATL_TRANSPORT=ofi CCL_RECV=direct CCL_SEND=direct CCL_ZE_IPC_EXCHANGE=pidfd CCL_TOPO_P2P_ACCESS=1
export CCL_SYCL_ALLREDUCE_LL=twoshots CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096
export CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296
export CCL_KERNEL_PATH=/opt/oneccl-4ceafd1-b70-public/lib/ccl/kernels
export FI_PROVIDER=tcp FI_TCP_IFACE=lo OMP_NUM_THREADS=1 PYTHONHASHSEED=0 PYTORCH_ALLOC_CONF=expandable_segments:True
export VLLM_NO_USAGE_STATS=1 VLLM_TARGET_DEVICE=xpu VLLM_USE_V1=1 VLLM_WORKER_MULTIPROC_METHOD=spawn
export VLLM_XPU_ENABLE_XPU_GRAPH=1 VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1 VLLM_XPU_MKLDNN_DETERMINISTIC=1
export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2 VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2 ZE_AFFINITY_MASK=0,1,2,3
export VLLM_TUNED_CONFIG_FOLDER=/opt/moe-m1-w13-n32
exec vllm serve "$model" --host 0.0.0.0 --port "$port" --served-model-name qwen38-flash-next-fp8-tp4 \
  --tokenizer "$model" --dtype bfloat16 --tensor-parallel-size 4 --pipeline-parallel-size 1 --data-parallel-size 1 \
  --distributed-executor-backend mp --enable-expert-parallel --all2all-backend allgather_reducescatter \
  --language-model-only --moe-backend triton \
  --compilation-config '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2,"compile_sizes":[],"cudagraph_num_of_warmups":1}' \
  --cudagraph-metrics --max-model-len 4352 --max-num-seqs 1 --max-num-batched-tokens 64 --no-enable-prefix-caching \
  --offload-backend uva --cpu-offload-gb 13.4 --cpu-offload-params ple_embedding.ngram_embedding.weight embed_tokens.weight mlp.experts \
  --gpu-memory-utilization 0.92 --kv-cache-memory-bytes 376569856 --kv-cache-dtype auto --block-size 64 \
  --generation-config vllm --load-format safetensors --no-async-scheduling --enable-prompt-tokens-details --disable-uvicorn-access-log \
  --speculative-config '{"method":"mtp","num_speculative_tokens":1}'
