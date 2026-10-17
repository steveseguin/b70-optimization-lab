#!/usr/bin/env bash
# Campaign 31 starter (2026-10-17, notes/2026-10-17-hostile-history-poison.md): waits for campaign 30 (unit
# ctx-campaign30) to end; starts nothing if its log shows an abort, a GPU fault line or a server that did not come up;
# clears the stop file used to end campaign 30's wait for more queue lines; then runs longrun-campaign31.sh once with
# queue 31 (ctxkeeper 1.1.1.dev0) on the same server settings, cards left empty at the end.
#   SUDO_ASKPASS=... systemd-run --user --unit=ctx-campaign31 ... bash run-20261017-campaign31.sh
set -uo pipefail
S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
O=/mnt/fast-ai/bench-results/context-longrun-20261016
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
say() { echo "### $(date +%H:%M:%S) $*"; }
for i in $(seq 1 720); do systemctl --user is-active --quiet ctx-campaign30 || break; sleep 10; done
systemctl --user is-active --quiet ctx-campaign30 && { say "campaign 30 still running after 2 h; campaign 31 not started"; exit 1; }
EV=$(grep -E "ABORT|GPU FAULT|GPU fault|server unit ended|did not come up|CUT at" "$O/c30.log")
[[ -n $EV ]] && { say "campaign 30 logged an event; campaign 31 not started"; echo "$EV" | head -5; exit 1; }
rm -f "$O/STOP-CAMPAIGN28"
[[ -n $(docker ps -q) ]] && { say "containers running; campaign 31 not started"; exit 1; }
say "campaign 30 ended clean; campaign 31 starting"
RUN=c31 SEQS=1 MTP=5 RESTORE=0 MARKS=1 QUEUE=$O/QUEUE31.txt bash "$S/longrun-campaign31.sh"
