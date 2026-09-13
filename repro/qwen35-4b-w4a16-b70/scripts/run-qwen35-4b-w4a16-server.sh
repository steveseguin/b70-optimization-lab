#!/usr/bin/env bash
# Qwen3.5-4B W4A16 (INT4 weights, FP16 activations) on Intel Arc Pro B70. Thin wrapper over the shared Qwen3.5 launcher:
# only the model directory and its manifest differ from the FP8 route. vLLM's compressed-tensors path selects
# CompressedTensorsWNA16, which on XPU is the lab's wNa16 kernel (_xpu_C.int4_gemm_w4a16) carrying the fixed-K two-tier
# W4A16 strategy. That kernel is row-count invariant, which is why this route stays byte-exact at every concurrency
# through 64 users where the FP8 route does not. No config relabel is needed (unlike AutoRound weights on the 27B lane).
#   MODEL_DIR  the downloaded RedHatAI/Qwen3.5-4B-quantized.w4a16 directory (required; verified against the manifest)
#   MTP_DEPTH / TENSOR_PARALLEL_SIZE / XPU_GRAPH / DRAFT_HEAD_INT4 / PORT and the rest: see the shared launcher.
#   DRAFT_SHORTLIST  container path of a token-id file for the draft head (default the 67k union list; empty = all rows)
#   CLASSPAD   0 (default): the published single-user configuration (R276 code path). 1: the class-consistent FP16 linear
#              (R293, 2026-09-11) - every unquantized linear, above all the 1.2 GB fp16 vocabulary projection, is padded or
#              split into one verified oneDNN M-class per weight shape instead of 32-row pieces that each re-read the weight.
#              Lossless by the same gates; 25-56% more throughput from about eight users up, 5-6% less at one user.
#              Details: repro/qwen35-4b-w4a16-b70/README.md (R293 section).
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo_root=$(cd -- "${script_dir}/../../.." && pwd)
export IMAGE=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304}
export EXPECTED_IMAGE_ID=${EXPECTED_IMAGE_ID:-sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2}
# R304 (2026-09-13): the served image is the runtime rebased onto stock vLLM XPU v0.29.0 (kernels 0.1.14.1 = this head); the
# image contract carries its own digest set keyed on this label. R294b (0.27.2 lineage) needs EXPECTED_KERNEL_HEAD=1e90ffa672ba02f17a909da11838a4c55b199783.
export EXPECTED_KERNEL_HEAD=${EXPECTED_KERNEL_HEAD:-6d92b1bfbf32767ecda8e819613eb151e70030ad}
# DRAFT_SHORTLIST (R294, 2026-09-12): the draft-only INT4 lm_head scores only these vocabulary rows; the target verifies
# every draft with its full FP16 head, so outputs cannot change. Default: the 67,248-row union list (27% of the
# vocabulary), +8% (4B) / +9% (9B) at one user with acceptance unchanged. DRAFT_SHORTLIST= (empty) scores every row.
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=${DRAFT_SHORTLIST-/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt}
export VLLM_XPU_FP16_LINEAR_CLASSPAD=${CLASSPAD:-0}
export MODEL_MANIFEST=${MODEL_MANIFEST:-${script_dir}/../manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen35-4b-w4a16-mtp${MTP_DEPTH:-3}} SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen35-4b-w4a16-mtp${MTP_DEPTH:-3}}
exec "${repo_root}/repro/qwen35-9b-fp8-b70/scripts/run-qwen35-9b-fp8-server.sh"
