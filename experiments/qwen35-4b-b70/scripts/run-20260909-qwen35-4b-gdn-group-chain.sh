#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 5 (2026-09-09): does the identity boundary sit at the GDN speculative group size?
#
# f3 measured the depth-3 c64-suite ladder at 8/12/16/20/24/32 and found a step, not a slope:
#
#   c8   0.00%   c12  1.39%   c16  1.04%   c20  9.17%   c24  9.03%   c32  7.29%
#
# Nine-fold, between c16 and c20. This lane runs VLLM_XPU_GDN_SPEC_GROUP=16, documented in
# repro/qwen38-27b-autoround-int4-b70 as "GDN speculative rows processed in groups of <=16 sequences".
# At or below 16 concurrent requests every speculative row is in one group; above it the rows are
# partitioned, and which group a request lands in depends on what else is in the batch. That predicts
# a boundary exactly where f3 found one.
#
# The test is a dose-response on the group size. If the boundary is the grouping, it moves with it:
#
#   group  8 -> step between c8  and c12
#   group 16 -> step between c16 and c20   (f3, already measured)
#   group 32 -> step between c32 and c40
#
# If instead the step stays between c16 and c20 at every group size, the grouping is not the cause and
# something else changes at 16-20 concurrent requests.
#
# Each arm also runs the engine's MTP0 ladder, which is a built-in negative control: the group size is
# a speculative-path setting and should do nothing without speculation.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-gdn-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-gdn-20260909.pid"
log() { printf '[gdn %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

log "waiting for chain 2"
while [[ ! -e "${out}/qwen35-4b-fragile-20260909-DONE" && ! -e "${out}/qwen35-4b-fragile-20260909-STOPPED" ]]; do sleep 60; done
[[ -e "${out}/qwen35-4b-fragile-20260909-STOPPED" ]] && { log "chain 2 stopped; not starting"; exit 1; }
log "chain 2 done"

wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10; }
hardware_abort() {
  [[ -f "$1/ABORTED" ]] || return 1
  grep -qiE 'not in normal state|fault signature|compute/XCCL health|container is still running|did not become healthy' "$1/ABORTED"
}
arm() {
  local label=$1; shift
  local root=${out}/qwen35-4b-w4a16-20260909-${label}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${label}: root already used, skipping"; return 0; }
  wait_free
  log "${label}: starting -> ${root}"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH=3 STAGES="ladders" \
      LADDER_CONCURRENCY="8,12,16,20,24,32,40" LADDER_REPEATS=10 "$@" \
      bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-gdn-20260909-STOPPED"; return 1
  fi
  return 0
}

# s16 repeats f3's group size at the same rungs and repeat count as the other two, so the three arms
# are matched and f3 is not doing double duty as both a data point and a differently-powered control.
arm s08 GDN_SPEC_GROUP=8  || exit 1
arm s16 GDN_SPEC_GROUP=16 || exit 1
arm s32 GDN_SPEC_GROUP=32 || exit 1

log "=== chain 5 complete ==="
echo done >"${out}/qwen35-4b-gdn-20260909-DONE"
