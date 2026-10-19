#!/bin/bash
# after-codex-run.sh <prefix> <READY> <proposal-glob (in ops/lane-queue)> <lane A|B> <launch UTC> <onecard|lane>
# Waits for codex-<prefix>-* to exit; requires a READY rewritten after <launch UTC> with ready_for_device true;
# resolves the proposal (READY 'proposals' entry matching the glob, else exactly one glob match); plans it on a temp copy.
# onecard: under a host-wide flock, full Codex freeze, rows run one at a time via hold-single.sh (stop on non-DONE).
# lane: append rows to queue-<lane>, selective freeze (codex-freeze-heavy.sh) until every row ends. Deadline 4 h.
set -u; cd /home/steve/llm-optimizations
PRE=$1; R=$2; G=$3; LANE=$4; T0=$(date -d "$5 UTC" +%s); MODE=$6
L=experiments/own-xpu-runtime/ops/lane-queue; FN=/tmp/claude-1000/-home-steve/fn-run; LOG=$FN/p58k.log; S=/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad
log(){ echo "$(date -u +%T) after-codex[$PRE] $*" >> $LOG; }; dl=$(( $(date +%s) + 4*3600 ))
while systemctl --user list-units --state=active --no-legend "codex-$PRE-*" | grep -q .; do [ $(date +%s) -gt $dl ] && { log deadline-codex; exit 3; }; sleep 20; done; sleep 10
R=$(ls -t $R 2>/dev/null | head -1); [ -n "$R" ] && [ -s $R ] && [ $(stat -c %Y $R) -gt $T0 ] || { log "no fresh READY; nothing queued"; exit 2; }
python3 -c "import json,sys;sys.exit(0 if json.load(open('$R')).get('ready_for_device') is True else 1)" || { log "READY not ready_for_device"; exit 2; }
F=$(python3 - "$R" "$G" "$L" "$LANE" <<'PY'
import json,sys,glob,os,fnmatch
r,g,L,lane=sys.argv[1:]; d=json.load(open(r)); c=set()
def walk(o):
    if isinstance(o,str) and fnmatch.fnmatch(os.path.basename(o),g): c.add(os.path.basename(o))
    elif isinstance(o,dict): [walk(k) or walk(v) for k,v in o.items()]
    elif isinstance(o,list): [walk(v) for v in o]
walk(d.get('proposals',d)); c={x for x in c if os.path.exists(os.path.join(L,x))}
if not c: c={os.path.basename(p) for p in glob.glob(os.path.join(L,g))}
if len(c)>1: c={x for x in c if f'-{lane}.' in x or f'-{lane}-' in x}
print(sorted(c)[0] if len(c)==1 else '')
PY
); [ -n "$F" ] || { log "ALERT proposal not uniquely resolved for $G"; exit 4; }
NAMES=$(python3 -c "import json;print(' '.join(json.loads(l)['name'] for l in open('$L/$F') if l.strip() and not l.startswith('#') and json.loads(l).get('lane','$LANE')=='$LANE'))")
[ -n "$NAMES" ] || { log "ALERT no lane-$LANE rows in $F"; exit 4; }
T=$(mktemp -d $S/acr.XXXX); python3 -c "
import json
rows=[l for l in open('$L/$F') if l.strip() and not l.startswith('#') and json.loads(l).get('lane','$LANE')=='$LANE']
open('$T/queue-$LANE.txt','w').writelines(rows)"
nice -n 19 taskset -c 8-15,24-31 python3 -B $L/lanequeue.py plan --lane $LANE --directory $T </dev/null > $T/plan.txt 2>&1 && ! grep -q FAILED $T/plan.txt || { log "ALERT plan failed: $(grep -o '"reason": "[^"]*"' $T/plan.txt | head -1 | cut -c1-200)"; exit 4; }
log "plan passed $F rows: $NAMES ($MODE)"
if [ "$MODE" = onecard ]; then
  exec 9>$FN/onecard-hold.lock; flock -w 14400 9 || { log "deadline onecard lock"; exit 3; }
  for nm in $NAMES; do
    t=$(( $(date +%s) + 300 )); while ls /home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1/active-lane-*.json >/dev/null 2>&1; do [ $(date +%s) -gt $t ] && { log "marker present; stop"; exit 3; }; sleep 10; done
    Z=""; for u in $(systemctl --user list-units --state=active --no-legend 'codex-*' | sed 's/^●//' | awk '{print $1}'); do systemctl --user freeze $u && Z="$Z $u"; done; log "codex frozen for $nm:$Z"
    bash $FN/hold-single.sh $F $nm
    for u in $Z; do systemctl --user thaw $u 2>/dev/null; done
    ev=$(grep "hold-single\[$nm\] $nm:" $LOG | tail -1 | grep -oE '"event": "[A-Z-]+"'); log "codex thawed; $nm $ev"
    echo "$ev" | grep -q '"DONE"' || { log "stop: $nm did not finish DONE"; exit 5; }; sleep 30
  done
else
  n=$(wc -l < $L/events-$LANE.jsonl); flock -w 30 $L/edit-$LANE.lock -c "cat $T/queue-$LANE.txt >> $L/queue-$LANE.txt"; log "queued on lane $LANE: $NAMES"
  SF=$T/stop; nohup bash $FN/codex-freeze-heavy.sh $SF 14400 >/dev/null 2>&1 &
  for nm in $NAMES; do until tail -n +$((n+1)) $L/events-$LANE.jsonl | grep "\"name\": \"$nm\"" | grep -qE '"event": "(DONE|FAILED|REFUSED|REFUSED-fast|REPORT-FAILED|REFUSED-PREDEVICE)'; do [ $(date +%s) -gt $dl ] && { touch $SF; log deadline-job; exit 3; }; sleep 15; done; done
  touch $SF; log "lane $LANE rows ended: $(tail -n +$((n+1)) $L/events-$LANE.jsonl | grep -oE '"event": "[A-Z-]+", "lane": "[AB]", "name": "[^"]+"' | grep -vE START | tr '\n' ' ' | cut -c1-300)"
fi
