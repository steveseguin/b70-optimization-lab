#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo=$(cd -- "${here}/../../.." && pwd)
export IMAGE=ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2
export DIGEST_REF="${IMAGE}"
export EXPECTED_IMAGE_ID=sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2
export EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad
export EXPECTED_XPU_EXTENSION_SHA256=bbce7295fb8a58bad456675cfac7cdf3d1e29fe7a9dd5c0970741b130616c932
export EXPECTED_XPU_OPS_SHA256=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3
export VLLM_USE_V2_MODEL_RUNNER=0 VLLM_XPU_FP16_LINEAR_CLASSPAD=0 VLLM_XPU_FP16_LINEAR_ROWCHUNK=32
export MAX_MODEL_LEN=33024 MAX_NUM_SEQS=1 MAX_NUM_BATCHED_TOKENS=4096
unset VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST
PACKAGE_DIR=packages/qwen38-27b-fp8-tp2-b70 LAUNCHER=experiments/qwen38-27b-b70/scripts/run-20260903-qwen38-fp8-mtp1-whole-graph-r187-server.sh SERVED_NAME=qwen38-27b-fp8 MODEL_DESC="Qwen/Qwen3.8-27B-FP8" MTP_DEPTH=1 PROFILES="two" \
exec "${repo}/tools/render-container-packet.sh"
