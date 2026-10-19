#!/bin/bash
# smoke-then-v5r.sh <codex-prefix> <READY json> <smoke proposal> <v5 proposal> <lane> <codex launch UTC> [rehearse_entry.py path]
# Variant: optional 7th arg = a packet-vendored rehearse_entry.py (packet-specific synthetic report streams); also requires READY ready_for_device true.
# After codex-<prefix> exits with a READY newer than its launch: plan+rehearse+queue the smoke; when the smoke is DONE (new events only), queue the v5.
cd /home/steve/llm-optimizations
PRE=$1; R=$2; SM=$3; V5=$4; LANE=$5; T0=$(date -d "$6 UTC" +%s); REH=${7:-experiments/own-xpu-runtime/ops/rehearse_entry.py}
L=experiments/own-xpu-runtime/ops/lane-queue; S=/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad; LOG=/tmp/claude-1000/-home-steve/fn-run/p118-chain.log
log(){ echo "$(date -u +%T) smoke-then-v5r[$PRE] $*" >> $LOG; }
dl=$(( $(date +%s) + 6*3600 ))
while systemctl --user list-units --state=active --no-legend "codex-$PRE-*" | grep -q . ; do [ $(date +%s) -gt $dl ] && { log deadline; exit 3; }; sleep 20; done; sleep 10
[ -s $R ] && [ $(stat -c %Y $R) -gt $T0 ] || { log "no fresh READY; nothing queued"; exit 2; }
python3 -c "import json,sys;sys.exit(0 if json.load(open('$R')).get('ready_for_device') is True else 1)" || { log "READY not ready_for_device; nothing queued"; exit 2; }
q(){ local f=$1 T=$(mktemp -d $S/stv5.XXXX); grep -v '^#' $L/$f | grep . > $T/queue-$LANE.txt
  nice -n 19 taskset -c 8-15,24-31 python3 -B $L/lanequeue.py plan --lane $LANE --directory $T </dev/null > $T/plan.txt 2>&1 && ! grep -q FAILED $T/plan.txt || { log "ALERT plan failed $f: $(grep FAILED $T/plan.txt | head -1 | cut -c1-200)"; return 1; }
  nice -n 19 taskset -c 8-15,24-31 python3 -B $REH $L/$f --report </dev/null > $T/rh.log 2>&1 || { log "ALERT rehearse_entry --report failed $f"; return 1; }
  flock -w 30 $L/edit-$LANE.lock -c "cat $T/queue-$LANE.txt >> $L/queue-$LANE.txt"; tail -1 $T/queue-$LANE.txt | python3 -c "import sys,json;print(json.loads(sys.stdin.read())['name'])"; }
n=$(wc -l < $L/events-$LANE.jsonl); sname=$(q $SM) || exit 4; log "queued smoke $sname on lane $LANE"
until tail -n +$((n+1)) $L/events-$LANE.jsonl | grep "\"name\": \"$sname\"" | grep -qE '"event": "(DONE|FAILED|REFUSED|REFUSED-fast|REPORT-FAILED)'; do [ $(date +%s) -gt $dl ] && { log deadline; exit 3; }; sleep 20; done
tail -n +$((n+1)) $L/events-$LANE.jsonl | grep "\"name\": \"$sname\"" | tail -1 | grep -q '"DONE"' || { log "smoke $sname did not pass; no bracket"; exit 5; }
vname=$(q $V5) || exit 4; log "smoke exact -> queued v5 $vname on lane $LANE"
