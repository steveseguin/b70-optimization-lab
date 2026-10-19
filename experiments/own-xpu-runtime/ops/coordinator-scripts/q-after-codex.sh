#!/bin/bash
# q-after-codex.sh <codex-prefix> <READY> <proposal> <lane> <launch UTC> [rehearse path]: after codex-<prefix> exits with a fresh READY (ready_for_device true): plan + rehearse + queue ONE proposal.
cd /home/steve/llm-optimizations
PRE=$1; R=$2; F=$3; LANE=$4; T0=$(date -d "$5 UTC" +%s); REH=${6:-experiments/own-xpu-runtime/ops/rehearse_entry.py}
L=experiments/own-xpu-runtime/ops/lane-queue; S=/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad; LOG=/tmp/claude-1000/-home-steve/fn-run/p118-chain.log
log(){ echo "$(date -u +%T) q-after-codex[$PRE] $*" >> $LOG; }; dl=$(( $(date +%s) + 3*3600 ))
while systemctl --user list-units --state=active --no-legend "codex-$PRE-*" | grep -q . ; do [ $(date +%s) -gt $dl ] && { log deadline; exit 3; }; sleep 20; done; sleep 10
[ -s $R ] && [ $(stat -c %Y $R) -gt $T0 ] || { log "no fresh READY; nothing queued"; exit 2; }
python3 -c "import json,sys;sys.exit(0 if json.load(open('$R')).get('ready_for_device') is True else 1)" || { log "READY not ready_for_device"; exit 2; }
T=$(mktemp -d $S/qac.XXXX); grep -v '^#' $L/$F | grep . > $T/queue-$LANE.txt
nice -n 19 taskset -c 8-15,24-31 python3 -B $L/lanequeue.py plan --lane $LANE --directory $T </dev/null > $T/plan.txt 2>&1 && ! grep -q FAILED $T/plan.txt || { log "ALERT plan failed: $(grep -o '"reason": "[^"]*"' $T/plan.txt | head -1 | cut -c1-200)"; exit 4; }
nice -n 19 taskset -c 8-15,24-31 python3 -B $REH $L/$F --report </dev/null > $T/rh.log 2>&1 || { log "ALERT rehearse failed $F"; exit 4; }
flock -w 30 $L/edit-$LANE.lock -c "cat $T/queue-$LANE.txt >> $L/queue-$LANE.txt"; log "queued $(python3 -c "import json;print(json.loads(open('$T/queue-$LANE.txt').readline())['name'])") on lane $LANE"
