#!/bin/bash
# One-card whole-host session (review 35/36 order): after packet157's lane-A smoke/split finish, run
# packet58aj smoke -> packet58aj v5 (ALL Codex frozen during the v5) -> packet58ai census; every wait has a deadline; always releases.
cd /home/steve/llm-optimizations
L=experiments/own-xpu-runtime/ops/lane-queue; C=/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1; LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log; S=/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad
CH=/tmp/claude-1000/-home-steve/fn-run/p118-chain.log
log(){ echo "$(date -u +%T) hold-onecard4 $*" >> $LOG; }
thaw(){ for u in $(systemctl --user list-units --no-legend 'codex-*' | sed 's/^●//' | awk '{print $1}'); do systemctl --user thaw $u 2>/dev/null; done; }
release(){ thaw; grep -q 'onecard4 whole-host' $L/PAUSE-B 2>/dev/null && rm -f $L/PAUSE-B; log "released: $1"; }
ready(){ python3 -c "import json,sys;sys.exit(0 if json.load(open('$1')).get('ready_for_device') is True else 1)"; }
dl0=$(( $(date +%s) + 2*3600 ))
# 1. wait for packet157's waiter to finish its lane-A sequence (smoke failed, or split queued and then terminal)
until grep -qE "smoke-then-v5r\[p157b\] (smoke .* did not pass|smoke exact -> queued v5)" $CH; do [ $(date +%s) -gt $dl0 ] && { log "deadline waiting for p157"; exit 3; }; sleep 15; done
while [ -e $L/PAUSE-A ] || [ -s $L/queue-A.txt ] || [ -e $L/inflight-A.json ] || [ -e $C/active-lane-A.json ]; do [ $(date +%s) -gt $dl0 ] && { log deadline-laneA; exit 3; }; sleep 15; done
for r in experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/READY-FOR-DEVICE.json experiments/own-xpu-runtime/stage2/packet58ai-miss-census/READY-FOR-DEVICE.json; do ready $r || { log "READY not true: $r"; exit 2; }; done
T=$(mktemp -d $S/hold1c4.XXXX)
for f in proposed-p58aj-smoke-A.txt proposed-p58aj-v5-A.txt proposed-p58ai-census-A.txt; do
  grep -v '^#' $L/$f | grep . > $T/$f.q; cp $T/$f.q $T/queue-A.txt
  nice -n 19 taskset -c 8-15,24-31 python3 -B $L/lanequeue.py plan --lane A --directory $T </dev/null > $T/plan-$f.txt 2>&1 && ! grep -q FAILED $T/plan-$f.txt || { log "ALERT plan failed $f"; exit 4; }
  nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/rehearse_entry.py $L/$f --report </dev/null > $T/rh-$f.log 2>&1 || { log "ALERT rehearse failed $f: $(grep FAIL $T/rh-$f.log | head -1 | cut -c1-150)"; exit 4; }
done
name(){ python3 -c "import json;print(json.loads(open('$1').readline())['name'])"; }
sm=$(name $T/proposed-p58aj-smoke-A.txt.q); v5=$(name $T/proposed-p58aj-v5-A.txt.q); ce=$(name $T/proposed-p58ai-census-A.txt.q)
echo "held for onecard4 whole-host session: packet58aj smoke/v5 + packet58ai census (coordinator $(date -u +%FT%TZ))" > $L/PAUSE-B
dl=$(( $(date +%s) + 3*3600 ))
while [ -e $L/inflight-B.json ] || [ -e $C/active-lane-B.json ]; do [ $(date +%s) -gt $dl ] && { release deadline-laneB; exit 3; }; sleep 10; done
n=$(wc -l < $L/events-A.jsonl); term(){ tail -n +$((n+1)) $L/events-A.jsonl | grep "\"name\": \"$1\"" | grep -E '"event": "(DONE|FAILED|REFUSED|REFUSED-fast|REPORT-FAILED|REFUSED-PREDEVICE)' | tail -1; }
waitjob(){ until [ -n "$(term $1)" ]; do [ $(date +%s) -gt $dl ] && { release "deadline $1"; exit 3; }; sleep 10; done; term $1 | grep -oE '"event": "[A-Z-]+"'; }
flock -w 30 $L/edit-A.lock -c "cat $T/proposed-p58aj-smoke-A.txt.q $T/proposed-p58aj-v5-A.txt.q >> $L/queue-A.txt"; log "queued $sm + $v5"
r=$(waitjob $sm); log "smoke $sm: $r"
if echo "$r" | grep -q DONE; then
  F=""; for u in $(systemctl --user list-units --state=active --no-legend 'codex-*' | awk '{print $1}'); do systemctl --user freeze $u && F="$F $u"; done; log "codex frozen for v5:$F"
  r=$(waitjob $v5); log "v5 $v5: $r"; thaw; log "codex thawed"
else
  flock -w 30 $L/edit-A.lock -c "python3 -c \"import json;q='$L/queue-A.txt';r=[l for l in open(q) if l.strip() and json.loads(l)['name']!='$v5'];open(q,'w').write(''.join(r))\""; log "v5 dropped"
fi
sleep 20
if [ -e $L/PAUSE-A ] || [ -e $C/active-lane-A.json ] || ls experiments/own-xpu-runtime/stage2/screen/v3/fault-*.json >/dev/null 2>&1; then release "marker/latch present; census skipped"; exit 5; fi
systemctl --user list-units --state=active --no-legend "lanequeue-A*" | grep -q . || { release "lane-A driver not active; census skipped"; exit 5; }
flock -w 30 $L/edit-A.lock -c "cat $T/proposed-p58ai-census-A.txt.q >> $L/queue-A.txt"; log "queued $ce"
r=$(waitjob $ce); log "census $ce: $r"; sleep 20; release done
