#!/usr/bin/env bash
# Campaign 30 starter (2026-10-17, notes/2026-10-17-hostile-history-poison.md): waits for the hang-repro3 stress hour
# (unit ctx-hang-repro3) to end, starts nothing if that run logged a failed request, a breadcrumb stall, an abort or a
# GPU fault line (the evidence is read first), else runs longrun-campaign28.sh once with queue 30 on the c28f/c29a
# server plus device marks, cards left empty at the end.
#   SUDO_ASKPASS=... systemd-run --user --unit=ctx-campaign30 ... bash run-20261017-campaign30.sh
set -uo pipefail
S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
O=/mnt/fast-ai/bench-results/context-longrun-20261016
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
say() { echo "### $(date +%H:%M:%S) $*"; }
for i in $(seq 1 540); do systemctl --user is-active --quiet ctx-hang-repro3 || break; sleep 10; done
systemctl --user is-active --quiet ctx-hang-repro3 && { say "ctx-hang-repro3 still running after 90 min; campaign 30 not started"; exit 1; }
EV=$(grep -E "failed request|breadcrumb blocks|GPU FAULT|ABORT|not ready|STALL" "$O/c29-hang-repro3.log")
[[ -n $EV ]] && { say "hang-repro3 logged an event; campaign 30 not started (read the evidence first)"; echo "$EV" | head -5; exit 1; }
grep -q "kernel log clean" "$O/c29-hang-repro3.log" || { say "hang-repro3 did not report a clean kernel log; campaign 30 not started"; tail -3 "$O/c29-hang-repro3.log"; exit 1; }
[[ -n $(docker ps -q) ]] && { say "containers running; campaign 30 not started"; exit 1; }
say "hang-repro3 ended clean; campaign 30 starting"
RUN=c30 SEQS=1 MTP=5 RESTORE=0 MARKS=1 QUEUE=$O/QUEUE30.txt bash "$S/longrun-campaign28.sh"
