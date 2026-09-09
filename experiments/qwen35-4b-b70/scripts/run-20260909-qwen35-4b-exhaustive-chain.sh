#!/usr/bin/env bash
# Qwen3.5-4B W4A16 exhaustive campaign (2026-09-09). One unattended runner per AGENTS.md rule 4.
# Preregistration: experiments/qwen35-4b-b70/notes/2026-09-09-qwen35-4b-exhaustive-preregistration.md
#
# Re-reading the 2026-09-07 ladders showed the c32+ identity break is speculation-driven (MTP0 is exact
# through c32 in all four passes, MTP3 breaks in all four), and that the three MTP0 c64 flips are not
# near-ties: one is a single inserted phantom token, one a four-token deletion, one a content divergence.
# This runner puts a rate on that, tests whether the decode-only graph capture is responsible, and then
# closes the dimensions the lane never measured (TP2 replication, TP2 long context, crossover, c>64).
#
# Arms run in priority order so a mid-chain hardware fault costs the least valuable work.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-exhaustive-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json

# The 4B is far smaller than the 9B this default was written for; a 11500 MiB gate would idle the chain
# for five minutes per server on a 15.5 GiB host for no reason.
export LOAD_MEMORY_MIB=7000

echo $$ >"${out}/qwen35-4b-exhaustive-20260909.pid"

log() { printf '[chain %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

# Wait for the cards to be free. Only ever look at RUNNING containers: dozens of exited qwen38
# containers exist on this host, and `docker ps -a` would block forever. Never pgrep a pattern that
# also appears in this script's own command line.
wait_free() {
  local waited=0
  while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do
    sleep 30; waited=$((waited+30))
    (( waited % 300 == 0 )) && log "waiting for cards, ${waited}s"
  done
  sleep 10
}

# Continue the chain when an arm aborts on a gate (that is a result); stop the chain when it aborts for
# a hardware reason, because every later arm would measure a degraded card.
hardware_abort() {
  local root=$1
  [[ -f "${root}/ABORTED" ]] || return 1
  grep -qiE 'not in normal state|fault signature|compute/XCCL health|container is still running|did not become healthy' "${root}/ABORTED"
}

arm() {
  local label=$1; shift
  local root=${out}/qwen35-4b-w4a16-20260909-${label}
  if [[ -e "${root}/campaign-end.txt" ]]; then log "${label}: already complete, skipping"; return 0; fi
  if [[ -e "${root}/campaign-start.txt" ]]; then log "${label}: root already used, skipping"; return 0; fi
  wait_free
  log "${label}: starting -> ${root}"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 "$@" \
      bash "${engine}" >>"${wrap}" 2>&1
  local rc=$?
  log "${label}: engine exit ${rc}"
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping the chain"; log "$(cat "${root}/ABORTED")"
    echo "chain stopped after ${label}" >"${out}/qwen35-4b-exhaustive-20260909-STOPPED"
    return 1
  fi
  [[ -f "${root}/ABORTED" ]] && log "${label}: gate abort (recorded, continuing): $(cat "${root}/ABORTED")"
  return 0
}

log "=== Qwen3.5-4B W4A16 exhaustive chain starting; boot $(cat /proc/sys/kernel/random/boot_id) ==="

# F1 rate and classification at the identity boundary. 20 repeats of c32/c64 on both the MTP3 and the
# MTP0 ladder; the engine's `ladders` stage runs the speculative arm then the no-speculation arm.
arm f1 TP=1 DEPTH=3 GRAPH=1 STAGES="ladders" \
    LADDER_CONCURRENCY="32,64" LADDER_REPEATS=20 || exit 1

# F2 the same measurement with the XPU decode graph off (piecewise Inductor). If the flips vanish the
# capture path is implicated; if the rate is unchanged it is not.
arm f2 TP=1 DEPTH=3 GRAPH=0 STAGES="ladders" \
    LADDER_CONCURRENCY="32,64" LADDER_REPEATS=20 || exit 1

# T3 two more TP2 strict passes to resolve the 5.7% spread in the published pair.
arm t3 TP=2 DEPTH=3 GRAPH=1 STAGES="strict" || exit 1

# F3 locate the speculation crossover. c16 is the disputed rung (937 vs 1090 in the two published passes).
arm f3 TP=1 DEPTH=3 GRAPH=1 STAGES="ladders" \
    LADDER_CONCURRENCY="8,12,16,20,24,32" LADDER_REPEATS=6 || exit 1

# T4 the real-content 2K-32K depth ladder on two cards; it has only ever run on one.
arm t4 TP=2 DEPTH=3 GRAPH=1 STAGES="depth32k" || exit 1

# F4 past c64. CAPTURE_SIZES and CAPTURE_MAX must rise together or an uncaptured decode shape falls back
# to eager, which is a different execution path and would confound the ladder.
arm f4 TP=1 DEPTH=3 GRAPH=1 STAGES="ladders" \
    CAPTURE_SIZES="1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64,80,96,112,128" CAPTURE_MAX=128 \
    LADDER_CONCURRENCY="64,96,128" LADDER_REPEATS=6 LADDER_MNS=128 LADDER_MBT=1024 || exit 1

log "=== chain complete ==="
echo done >"${out}/qwen35-4b-exhaustive-20260909-DONE"
