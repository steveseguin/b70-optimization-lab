#!/usr/bin/env bash

if [[ ${ALLOW_CONCURRENT_MODEL_WORKLOADS:-0} != 1 ]] && pgrep -x llama-server >/dev/null; then
    printf 'Refusing to start a second llama.cpp model workload on this low-RAM host.\n' >&2
    return 1
fi

set +u
source /opt/intel/oneapi/tbb/2023.1/env/vars.sh >/dev/null
source /opt/intel/oneapi/compiler/2026.1/env/vars.sh >/dev/null
source /opt/intel/oneapi/mkl/2026.1/env/vars.sh >/dev/null
source /opt/intel/oneapi/umf/1.0/env/vars.sh >/dev/null
set -u

export GGML_SYCL_DISABLE_DNN=1
export GGML_SYCL_ENABLE_DNN=0
export GGML_SYCL_ENABLE_OPT=1
export GGML_SYCL_ENABLE_FUSION=1
export GGML_SYCL_ENABLE_MMQ=1
export GGML_SYCL_ENABLE_VMM=1
export GGML_SYCL_USE_LEVEL_ZERO_API=1
export GGML_SYCL_USE_ASYNC_MEM_OP=1
export GGML_SYCL_USM_SYSTEM=0
export GGML_SYCL_MMQ_Q8_REORDER=1
export GGML_SYCL_MMVQ_Q8_WIDE=1
export GGML_SYCL_MMVQ_PAD=1
export GGML_SYCL_MMVQ_SPLIT=1
export GGML_SYCL_MMVQ_SPLIT_AT=0
export GGML_SYCL_MMVQ_CHUNK=-1
export GGML_SYCL_MMVQ_SHAPE_CAP=1
export GGML_SYCL_MMVQ_SG32="${GGML_SYCL_MMVQ_SG32:-0}"
export GGML_SYCL_MMVQ_Q8_QUAD_SG16="${GGML_SYCL_MMVQ_Q8_QUAD_SG16:-1}"
export GGML_SYCL_MMVQ_Q8_QUAD_SG24="${GGML_SYCL_MMVQ_Q8_QUAD_SG24:-1}"
export GGML_SYCL_MMVQ_PHASE=-1
export GGML_SYCL_Q8_QUANT_DEDUP=1
export GGML_SYCL_FATTN_MMA=1
export GGML_SYCL_FATTN_QKV_TILE=0
export GGML_SYCL_DETERMINISTIC=1
export GGML_SYCL_INPUT_ASYNC=0
export GGML_SYCL_SET_TENSOR_STAGING=1
export GGML_SYCL_SET_TENSOR_STAGING_MB=64
export GGML_SYCL_ENABLE_GRAPH=0

unset GGML_SYCL_ASYNC_CPY_TENSOR
unset GGML_SYCL_FATTN_NSM_LEGACY
unset GGML_SYCL_MMQ_CAP
unset GGML_SYCL_MMVQ_CAP
unset GGML_SYCL_MMVQ_WIDE
unset SYCL_CACHE_PERSISTENT
