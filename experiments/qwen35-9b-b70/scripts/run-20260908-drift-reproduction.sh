#!/usr/bin/env bash
# Runner for the offline drift probe, so the invocation is recorded rather than retyped.
#
# The probe's first five runs were launched by hand and compared a 64-token prefix of a 128-token
# generation. In the ladder data the median first divergence is at token 90, so that window could not
# have shown the effect whatever the batch did. COMPARE now defaults to the full generation; this
# script pins the rest of the configuration to what the fragile-site ladder actually ran.
#
# 2026-09-09: the first full-window attempt (2026-09-08 14:07 UTC) died in oneCCL with "opendir failed:
# could not open device directory" - the strict launchers set CCL_ZE_IPC_EXCHANGE=pidfd and the rest of
# the oneCCL transport environment, and this runner did not, so the TP2 worker could not exchange IPC
# handles. The same lines run-server.sh uses are now here.
set -uo pipefail
repo=/home/steve/b70-optimization-lab
M9=/home/steve/llm-models/qwen35-9b-w4a16
BOTH=neural-download/vllm-openai-xpu:qwen38-int4-r276-both-diag
SUITE=$repo/experiments/qwen35-9b-b70/data/2026-09-08-fragile-tie-site-suite-v1.json
OUT=${OUT:-/mnt/fast-ai/bench-results/drift-reproduction}
mkdir -p "$OUT"

run() { # $1=label $2=DRIFT $3=extra env
  echo "=== arm $1 (drift=$2) $(date --iso-8601=seconds)"
  docker run --rm --network host --entrypoint python3 \
    --ulimit core=0 \
    --device /dev/dri:/dev/dri \
    --group-add render \
    --cap-add SYS_PTRACE \
    --security-opt label=disable \
    --ipc=host --shm-size=8g \
    -v "$M9":/model:ro -v "$SUITE":/suite.json:ro \
    -v "$repo/experiments/qwen35-9b-b70/probes":/probes:ro \
    -e ZE_AFFINITY_MASK=0,1 -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
    -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
    -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e CCL_ZE_IPC_EXCHANGE=pidfd \
    -e CCL_SEND=direct -e CCL_RECV=direct -e CCL_TOPO_P2P_ACCESS=1 \
    -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
    -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
    -e DRIFT="$2" -e SUITE=/suite.json -e REQUESTS="${REQUESTS:-64}" \
    -e CAP_MAX="${CAP_MAX:-128}" -e TP="${TP:-2}" \
    -e MAX_MODEL_LEN="${MAX_MODEL_LEN:-512}" \
    -e MAX_BATCHED_TOKENS="${MAX_BATCHED_TOKENS:-8192}" \
    ${3:-} "$BOTH" \
    /probes/drift-reproduction.py 2>&1 | tee "$OUT/$1.log" | tail -25
}

run lockstep-full 0
run drift-full 1
