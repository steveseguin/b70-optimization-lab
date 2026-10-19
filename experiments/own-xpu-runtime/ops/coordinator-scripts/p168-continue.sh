#!/bin/bash
# When codex-p168 exits: if its READY is not true, launch Codex p168b, then queue p168b's lane-B row via after-codex-run.sh (lane mode).
cd /home/steve/llm-optimizations; FN=/tmp/claude-1000/-home-steve/fn-run; LOG=$FN/p58k.log; log(){ echo "$(date -u +%T) p168-continue $*" >> $LOG; }
R=experiments/own-xpu-runtime/stage2/packet168-twocard-body-census/READY-FOR-DEVICE.json; dl=$(( $(date +%s) + 3*3600 ))
while systemctl --user list-units --state=active --no-legend "codex-p168-*" | grep -q .; do [ $(date +%s) -gt $dl ] && { log deadline; exit 3; }; sleep 20; done; sleep 15
python3 -c "import json,sys;sys.exit(0 if json.load(open('$R')).get('ready_for_device') is True else 1)" 2>/dev/null && { log "p168 READY true; after-codex[p168] handles queueing"; exit 0; }
T=$(date -u '+%Y-%m-%d %H:%M:%S'); U=codex-p168b-$(date +%H%M%S); systemd-run --user --unit=$U /usr/bin/bash $FN/codex-launch2.sh p168b >/dev/null 2>&1; log "p168 not ready; launched $U"; sleep 30
bash $FN/after-codex-run.sh p168b "$R" 'proposed-p168*.txt' B "$T" lane
