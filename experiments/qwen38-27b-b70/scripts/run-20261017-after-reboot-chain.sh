#!/usr/bin/env bash
# Runs inside the unit that run-20261017-after-reboot.sh starts (ctx-after-reboot), so the morning's queue goes on
# after the owner's reboot without a session watching it:
#   1. campaign 28f (longrun-campaign28.sh with the env the unit was given: 0.3.0 check on K32, then the repair task)
#   2. if this boot's kernel log is still clean: the step-floor study (run-20261017-step-floor.sh, six servers)
# Cards are left empty at the end; Gemma is not restored (owner's call after the faults of 2026-10-17).
set -uo pipefail
E=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70
O=/mnt/fast-ai/bench-results/context-longrun-20261016
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
faults() { sudo -A journalctl -k -b --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }

say "chain: campaign 28f"
(cd "$E/scripts" && bash "$E/scripts/longrun-campaign28.sh") >> "$O/c28f.log" 2>&1
rc=$?
say "chain: campaign 28f exited rc $rc"
[[ -n $(faults) ]] && { say "chain: fault line on this boot after 28f; step-floor study NOT run (AGENTS.md rule 3)"; faults | head -5; exit 1; }
[[ -n $(docker ps -q) ]] && { say "chain: containers still running after 28f; step-floor study NOT run"; exit 1; }
sleep 30
say "chain: step-floor study"
env -u RUN -u QUEUE -u EDIT -u MTP -u SEQS -u ONE_LAUNCH -u TAIL -u IDLE_MAX \
  bash "$E/scripts/run-20261017-step-floor.sh" >> "$O/step-floor.log" 2>&1
say "chain: step-floor study exited rc $?"
