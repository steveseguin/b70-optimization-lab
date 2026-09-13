#!/usr/bin/env bash
# Preregistered R308 4B same-image strict qualification; run after the isolated
# R308 boundary + 9B campaign has completed and released the host.
# Four fresh servers/caches: MTP0 a/b, then fixed-depth-3 a/b; TP1 card 0,
# max_model_len=1024, max_num_seqs=1, FULL_DECODE_ONLY, CLASSPAD=0,
# draft INT4 head + union shortlist, unchanged W4A16 target and verifier.
# The common engine owns preflight, kernel-journal startup checks, server
# cleanup, postflight, and G1/G2/G3a/G3b (each must be 12/12). Workload,
# cache/canary or any health failure aborts. Throughput is recorded, not gated.
# This script never queues behind or changes an active campaign: a busy host
# fails preflight. RUN_ROOT must be unused; completion is campaign-end.txt.
set -Eeuo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
image=sha256:b9bbb5190f6dd47973501e61aa129706c92345b310eeec4537a20256eba424ba
root=${RUN_ROOT:-/mnt/fast-ai/bench-results/r308-4b-independent-strict-20260913}
# Require an empty host, including containers outside the lane-name patterns
# recognized by the historical common engine.
running_containers=$(docker ps -q)
[[ -z "${running_containers}" ]] || { echo 'ABORT: another container is running' >&2; exit 2; }
[[ ! -e "${root}/campaign-start.txt" ]] || { echo "ABORT: reused campaign root: ${root}" >&2; exit 2; }
export LANE=qwen35-4b-w4a16 MODEL_DIR=/home/steve/llm-models/qwen35-4b-w4a16
export MODEL_MANIFEST=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
export QUANT=compressed-tensors IMAGE=${image} IMAGE_ID=${image}
export RUN=r308-4b-qualified ROOT=${root} PORT=18131 XPU_DEVICE_MASK=0
export DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH=3 STAGES=strict
export LOAD_MEMORY_MIB=11500 SKIP_IMAGE_CONTRACT=0
export EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad
export VLLM_USE_V2_MODEL_RUNNER=0 VLLM_XPU_FP16_LINEAR_CLASSPAD=0
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt
# timeout forwards TERM to its process group; the engine's EXIT trap owns
# container cleanup. The grace period exceeds its 60-second stop timeout.
timeout --signal=TERM --kill-after=120s 3600 bash "${engine}"
[[ -e "${root}/campaign-end.txt" && ! -e "${root}/ABORTED" ]] || {
  echo 'ABORT: engine returned without a clean completion artifact' >&2
  exit 2
}
printf 'R308 4B strict qualification complete: %s\n' "${root}"
