#!/usr/bin/env bash
# 2026-10-17 hang replay (registered in notes/2026-10-17-hang-repro.md before it ran): campaign 28e rebuilt exactly
# (same runner, queue line "K32 repair 2x 3600", server flags, depth 5, piece 832, one launch, tail switch, one
# sequence, and the exact-cache overlay at 0.2.0 as c28e ran it), plus b70-step-breadcrumbs 0.2.0. If the 06:23 hang
# follows from the inputs, it comes back at the same call (c28e call 126 of the main stream, a 4,603-token request
# with a 4,160-token hit). Waits for the hang-repro unit to finish first; on the first kernel fault line copies every
# card's device coredump before anything else. The campaign starts its server once and leaves the cards empty.
#   SUDO_ASKPASS=... systemd-run --user --unit=ctx-hang-replay ... bash run-20261017-hang-replay.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
S=$LAB/experiments/qwen38-27b-b70/scripts
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-17-hang-replay
O=/mnt/fast-ai/bench-results/context-longrun-20261016
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost|failed to respond)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
mkdir -p "$D"

for i in $(seq 1 720); do systemctl --user is-active --quiet ctx-hang-repro || break; sleep 5; done
systemctl --user is-active --quiet ctx-hang-repro && { say "hang-repro unit still running after 1 h; nothing run"; exit 1; }
[[ -n $(docker ps -q) ]] && { say "containers running; nothing run"; docker ps --format '{{.Names}} {{.Image}}'; exit 1; }
[[ -e $O/server/tp2-w262144-s1-xp-mtp5-p832-c28r ]] && { say "c28r server folder exists; nothing run"; exit 1; }
F=$(sudo -A journalctl -k --since "-75 min" --no-pager 2>/dev/null | grep -Ei "$FAULT_RE")
[[ -n $F ]] && { say "kernel fault lines in the last 75 min; nothing run (read them first)"; echo "$F" | head -5; exit 1; }

START=$(date '+%F %T')
say "replay of c28e as c28r; MemAvailable $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"
( # watchdog: first fault line -> copy every card's device coredump, the kernel log and the server log end
  while [[ ! -e $D/.campaign-done ]]; do
    if sudo -A journalctl -k --since "$START" --no-pager 2>/dev/null | grep -qEi "$FAULT_RE"; then
      sleep 4
      for c in /sys/class/drm/card*/device; do
        p=$(basename "$(readlink -f "$c")")
        [[ -e $c/devcoredump/data ]] && sudo -A cat "$c/devcoredump/data" > "$D/devcoredump-$p.txt" 2>/dev/null
      done
      sudo -A journalctl -k --since "$START" --no-pager -o short-precise > "$D/kernel.txt" 2>/dev/null
      tail -600 "$O/server/tp2-w262144-s1-xp-mtp5-p832-c28r/server.log" > "$D/server-log-end.txt" 2>/dev/null
      grep -A80 "b70_step_breadcrumbs rank" "$O/server/tp2-w262144-s1-xp-mtp5-p832-c28r/server.log" > "$D/crumbs.txt" 2>/dev/null
      say "fault seen: coredumps copied ($(ls "$D" | grep -c devcoredump) files), kernel log and breadcrumbs saved"
      break
    fi
    sleep 2
  done ) &
WD=$!
RUN=c28r MTP=5 SEQS=1 ONE_LAUNCH=1 TAIL=1 EDIT=0 RESTORE=0 IDLE_MAX=5 QUEUE=$O/QUEUE28d.txt \
  EXACT_OVERLAY=b70-prefix-cache-exact-020 BREADCRUMBS=1 bash $S/longrun-campaign28.sh > "$O/c28r.log" 2>&1
rc=$?
touch "$D/.campaign-done"
sleep 6
kill $WD 2>/dev/null
cp "$O/c28r.log" "$D/c28r.log"
P=$(ls -d $O/proxy-state/c28r-K32-repair-s2x/*/ 2>/dev/null | head -1)
[[ -n $P ]] && cp "$P/calls.jsonl" "$D/calls-c28r.jsonl"
grep -A80 "b70_step_breadcrumbs rank" "$O/server/tp2-w262144-s1-xp-mtp5-p832-c28r/server.log" > "$D/crumbs.txt" 2>/dev/null
python3 $S/compare-call-sequences.py "$O/proxy-state/c28e-K32-repair-s2x/5693d81e7626fa3b/calls.jsonl" "$D/calls-c28r.jsonl" \
  > "$D/compare-c28e-c28r.txt" 2>&1
cat "$D/compare-c28e-c28r.txt"
say "replay finished, campaign rc $rc"
exit 0
