#!/bin/bash
# autoq-ready.sh <ready-json> <proposal-basename> <lane>: when the READY-FOR-DEVICE file exists (and names the proposal's sha256 if it lists any),
# plan the proposal on a temp queue and append it to the lane's queue. Triggers on the ready file, not on Codex exiting (review 26).
cd /home/steve/llm-optimizations
R=$1; f=experiments/own-xpu-runtime/ops/lane-queue/$2; lane=$3; L=experiments/own-xpu-runtime/ops/lane-queue
S=/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad; LOG=/tmp/claude-1000/-home-steve/fn-run/p118-chain.log
log(){ echo "$(date -u +%T) autoq-ready[$2] $*" >> $LOG; }
dl=$(( $(date +%s) + 4*3600 ))
until [ -s $R ] && [ -s $f ]; do [ $(date +%s) -gt $dl ] && { log "deadline: no ready file"; exit 3; }; sleep 30; done
sleep 15
h=$(sha256sum $f | cut -d' ' -f1)
python3 - "$R" "$h" <<'PY' || { log "ALERT ready file does not name the current proposal sha256; not queued"; exit 5; }
import json,sys
d=json.load(open(sys.argv[1])); s=json.dumps(d)
shas=[v for v in __import__('re').findall(r'[0-9a-f]{64}',s)]
sys.exit(0 if (sys.argv[2] in shas or not any('propos' in k for k in json.dumps(d).split('"'))) else 1)
PY
T=$(mktemp -d $S/autoq-ready.XXXX); grep -v '^#' $f | grep . > $T/queue-$lane.txt
nice -n 19 taskset -c 8-15,24-31 python3 -B $L/lanequeue.py plan --lane $lane --directory $T </dev/null > $T/plan.txt 2>&1 && ! grep -q FAILED $T/plan.txt || { log "ALERT plan failed: $(grep FAILED $T/plan.txt | head -1 | cut -c1-150)"; exit 4; }
flock -w 30 $L/edit-$lane.lock -c "cat $T/queue-$lane.txt >> $L/queue-$lane.txt"; log "queued $(wc -l < $T/queue-$lane.txt) job(s) on lane $lane"
