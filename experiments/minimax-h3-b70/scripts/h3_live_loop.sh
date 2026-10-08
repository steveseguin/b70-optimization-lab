#!/usr/bin/env bash
# Live session for the stream: duet runs (one clip per prompt, two cards, one process each) back to
# back over PROMPTS_FILE with a stepping seed, until UNTIL (epoch seconds) passes or STOP-LIVE exists
# under OUT_ROOT.  h3_stream.py watching OUT_ROOT picks each finished clip up by its receipt.json.
# A new GPU fault line on this boot halts the loop (the H3 lane rule from gate-session-20261003.sh).
# CHAIN_AFTER=<command> runs when the loop ends (used to hand the cards back to the retention study).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT_ROOT="${OUT_ROOT:-/mnt/fast-ai/bench-results/minimax-h3}"
PROMPTS_FILE="${PROMPTS_FILE:-${HERE}/../data/live-prompts.txt}"
UNTIL="${UNTIL:-0}"; SEED="${SEED0:-1000}"; MAX_RUNS="${MAX_RUNS:-1000}"
LOG="${OUT_ROOT}/live-$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "${OUT_ROOT}"; rm -f "${OUT_ROOT}/STOP-LIVE"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "${LOG}"; }
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup|hard LOCKUP'
fault_count() { journalctl -k -b --no-pager 2>/dev/null | grep -ciE "${FAULT_RE}"; }
F0="$(fault_count)"
say "live loop: prompts=${PROMPTS_FILE} seed0=${SEED} until=$( [ "${UNTIL}" -gt 0 ] && date -d @"${UNTIL}" +%H:%M || echo none ) faults-on-boot=${F0}"
n=0; rc=0
while :; do
  [ -e "${OUT_ROOT}/STOP-LIVE" ] && { say "STOP-LIVE seen; ending"; break; }
  [ "${UNTIL}" -gt 0 ] && [ "$(date +%s)" -ge "${UNTIL}" ] && { say "deadline reached; ending"; break; }
  [ "${n}" -ge "${MAX_RUNS}" ] && { say "MAX_RUNS reached; ending"; break; }
  n=$((n + 1))
  say "---- run ${n}: seed ${SEED}"
  env HEIGHT=544 WIDTH=960 VAE_DECODE=two-proc SEED="${SEED}" PROMPTS_FILE="${PROMPTS_FILE}" OUT_ROOT="${OUT_ROOT}" \
      bash "${HERE}/smoke_h3.sh" duet > "${OUT_ROOT}/live-run-${n}.out" 2>&1 || rc=$?
  run="$(ls -dt "${OUT_ROOT}"/duet-2*/ 2>/dev/null | head -1 | xargs -r basename)"
  say "run ${n}: rc=${rc} run=${run} clips=$(ls -d "${OUT_ROOT}/${run}"/clip-*/receipt.json 2>/dev/null | wc -l)"
  grep -E 'PREFLIGHT FAIL|WATCHDOG KILLED' "${OUT_ROOT}/live-run-${n}.out" | tee -a "${LOG}"
  f="$(fault_count)"
  [ "${f}" -eq "${F0}" ] || { say "HALT: new GPU fault line(s) during run ${n} (${F0} -> ${f}); nothing reset"; rc=9; break; }
  [ "${rc}" -eq 0 ] || { say "run ${n} failed (rc=${rc}); ending the loop"; break; }
  SEED=$((SEED + 1))
done
say "live loop ended after ${n} run(s), rc=${rc}"
if [ -n "${CHAIN_AFTER:-}" ]; then say "chain: ${CHAIN_AFTER}"; bash -c "${CHAIN_AFTER}" 2>&1 | tee -a "${LOG}"; fi
exit "${rc}"
