#!/bin/bash
# hold-single.sh <proposal-file> <job-name>: whole-host one-card hold for ONE named row (queued alone), then release.
cd /home/steve/llm-optimizations
L=experiments/own-xpu-runtime/ops/lane-queue; C=/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1; LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log; S=/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad
F=$1; NM=$2; log(){ echo "$(date -u +%T) hold-single[$NM] $*" >> $LOG; }
release(){ grep -q "hold-single $NM" $L/PAUSE-B 2>/dev/null && rm -f $L/PAUSE-B; log "released: $1"; }
T=$(mktemp -d $S/hsingle.XXXX); python3 -c "
import json,sys
rows=[l for l in open('$L/$F') if l.strip() and not l.startswith('#') and json.loads(l)['name']=='$NM']
sys.exit(1) if len(rows)!=1 else open('$T/queue-A.txt','w').write(rows[0])" || { log "row not found"; exit 2; }
nice -n 19 taskset -c 8-15,24-31 python3 -B $L/lanequeue.py plan --lane A --directory $T </dev/null > $T/plan.txt 2>&1 && ! grep -q FAILED $T/plan.txt || { log "ALERT plan failed: $(grep -o '"reason": "[^"]*"' $T/plan.txt | head -1 | cut -c1-200)"; exit 4; }
dl=$(( $(date +%s) + 2*3600 ))
while [ -e $L/PAUSE-A ] || [ -s $L/queue-A.txt ] || [ -e $L/inflight-A.json ] || [ -e $C/active-lane-A.json ]; do [ $(date +%s) -gt $dl ] && { log deadline-laneA; exit 3; }; sleep 10; done
systemctl --user list-units --state=active --no-legend "lanequeue-A*" | grep -q . || { log "no lane-A driver"; exit 4; }
echo "held for hold-single $NM whole-host one-card (coordinator $(date -u +%FT%TZ))" > $L/PAUSE-B
while [ -e $L/inflight-B.json ] || [ -e $C/active-lane-B.json ]; do [ $(date +%s) -gt $dl ] && { release deadline-laneB; exit 3; }; sleep 10; done
n=$(wc -l < $L/events-A.jsonl); flock -w 30 $L/edit-A.lock -c "cat $T/queue-A.txt >> $L/queue-A.txt"; log "queued $NM (alone)"
until tail -n +$((n+1)) $L/events-A.jsonl | grep "\"name\": \"$NM\"" | grep -qE '"event": "(DONE|FAILED|REFUSED|REFUSED-fast|REPORT-FAILED|REFUSED-PREDEVICE)'; do [ $(date +%s) -gt $dl ] && { release deadline-job; exit 3; }; sleep 10; done
log "$NM: $(tail -n +$((n+1)) $L/events-A.jsonl | grep "\"name\": \"$NM\"" | tail -1 | grep -oE '"event": "[A-Z-]+"')"; sleep 20; release done
