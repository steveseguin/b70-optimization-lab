#!/usr/bin/env bash
# Qwen3.5-9B W4A16 on one B70, one server for every batch size: MTP depth 3 at 1-8 concurrent users, depth 1 at
# 9-16, no speculation above (vLLM's num_speculative_tokens_per_batch_size), on the R276 image plus two pure-Python
# overlays built from ../docker (dynamic-Mamba-allocation + full decode graphs per scheduled K). Measured 2026-09-10
# (campaigns fgdynm1 / fgdynm1r): 110.7 tok/s at one user (the static depth-3 headline), 623 aggregate at 8 users,
# ~1090 at 32 and ~1150 at 64 (no-speculation server: 1148 / 1208), byte-exact against the no-speculation oracle on
# the strict suite and on the 2K-32K real-content ladder, and exact through 16 users on the identity ladder in both
# runs (near-exact at 32 and 64, as the no-speculation server itself is).
#
# Build the image once (COPY-only Dockerfiles, no compiler, a few seconds each; the base is the public R276 digest):
#   docker build -f repro/qwen35-9b-w4a16-b70/docker/r276-dynamic-mamba-alloc.Dockerfile \
#     -t neural-download/vllm-openai-xpu:qwen38-int4-r276-dynamic-mamba-alloc repro/qwen35-9b-w4a16-b70/docker
#   docker build -f repro/qwen35-9b-w4a16-b70/docker/r276-dynsd-fullgraph.Dockerfile \
#     -t neural-download/vllm-openai-xpu:qwen38-int4-r276-dynsd-fullgraph repro/qwen35-9b-w4a16-b70/docker
# The image ID of a locally built overlay is not portable, so this launcher pins the CONTENT instead: it verifies the
# SHA-256 of every overlaid file inside the image before starting, and the base R276 kernels and pinned Python files
# are still verified by the shared launcher's image contract.
#   MODEL_DIR       the downloaded RedHatAI/Qwen3.5-9B-quantized.w4a16 directory (required)
#   SPEC_SCHEDULE   JSON list of [first_batch_size,last_batch_size,draft_tokens]; default [[1,8,3],[9,16,1],[17,64,0]]
#   MTP_DEPTH       the largest draft depth in the schedule (default 3); MAX_NUM_SEQS default 64 to cover the schedule
#   IMAGE           default neural-download/vllm-openai-xpu:qwen38-int4-r276-dynsd-fullgraph
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-r276-dynsd-fullgraph}
depth=${MTP_DEPTH:-3}
schedule=${SPEC_SCHEDULE:-[[1,8,3],[9,16,1],[17,64,0]]}
[[ "${depth}" =~ ^[1-9]$ ]] || { echo "MTP_DEPTH must be 1-9 for the schedule (got ${depth})" >&2; exit 1; }
[[ "${schedule}" =~ ^\[\[[0-9,\]\[]+\]\]$ ]] || { echo "SPEC_SCHEDULE must be a JSON list of [start,end,K] with no spaces" >&2; exit 1; }
# Pin the overlay by content. Digests are those of the files in ../docker (sha256sum r276-*.py).
declare -A want=(
  [v1/core/sched/scheduler.py]=6d550a8e6a5c6abf200d66fbc4fc45c8ce371a312d454c39e057a45b364994c3
  [v1/core/single_type_kv_cache_manager.py]=b9a100331f98882dc01dc6f6efac53b1fc1fc949ba0b8915e932336a8a521c09
  [config/vllm.py]=e03067d4fbcf56ae51fd254fb70c02a3cdf25fd3db6bae70855b945cdc15bcb2
  [v1/cudagraph_dispatcher.py]=3d296446deea8726643d7942f49cf920b82d26bb2205480190ef4d0a731bbb98
  [v1/worker/gpu_model_runner.py]=0d9546794241873204cc80de0a5918c6d430bb70f885e8919a2a8e0da3e94c7e
)
probe=qwen35-overlay-probe-$$
docker create --name "${probe}" "${image}" >/dev/null
trap 'docker rm "${probe}" >/dev/null 2>&1 || true' EXIT
for rel in "${!want[@]}"; do
  got=$(docker cp "${probe}:/opt/venv/lib/python3.12/site-packages/vllm/${rel}" - | tar -xO | sha256sum | cut -d' ' -f1)
  [[ "${got}" == "${want[$rel]}" ]] || { echo "overlay content mismatch: ${rel} is ${got}, expected ${want[$rel]}; rebuild from ../docker" >&2; exit 1; }
done
docker rm "${probe}" >/dev/null; trap - EXIT
export IMAGE="${image}" EXPECTED_IMAGE_ID=$(docker image inspect "${image}" --format '{{.Id}}')
export MTP_DEPTH="${depth}" MAX_NUM_SEQS=${MAX_NUM_SEQS:-64}
export SPECULATIVE_CONFIG="{\"method\":\"qwen3_5_mtp\",\"num_speculative_tokens\":${depth},\"num_speculative_tokens_per_batch_size\":${schedule}}"
export CONTAINER_NAME=${CONTAINER_NAME:-qwen35-9b-w4a16-dyn} SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen35-9b-w4a16-dyn}
exec "${script_dir}/run-qwen35-9b-w4a16-server.sh"
