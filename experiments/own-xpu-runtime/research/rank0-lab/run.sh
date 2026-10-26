#!/bin/bash
# run.sh NAME LAUNCH PROMPT ROWS [KEY=VALUE ...]: one rank-0 engine run on card 27 under the card lock, with a
# kernel-fault check before and after. Any matching fault line creates HALT and refuses subsequent runs.
set -uo pipefail
cd /dev/shm/ownrt-lab-r0
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/rank0-lab/tp_rank0_driver.py
PAT="Fault response|CAT error|engine reset|GPU HANG|wedged|Timedout"
name=$1; launch=$2; prompt=$3; rows=$4; shift 4
[ -e HALT ] && { echo "HALT present"; exit 3; }
last=$(cat last-check 2>/dev/null || echo $(( $(date +%s) - 3600 )))
if journalctl -k --since "@$last" --no-pager | grep -iE "$PAT"; then echo "FAULT LINES since last check"; touch HALT; exit 2; fi
L=launch-$launch.json
if [ $# -gt 0 ]; then python3 - "$L" "runs/launch-$name.json" "$@" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
for kv in sys.argv[3:]:
    k,v=kv.split('=',1)
    if k in('SPLIT','CONTEXT'):
        f='--target-split' if k=='SPLIT' else '--context';d['argv'][d['argv'].index(f)+1]=v
    else: d['environment'][k]=v
json.dump(d,open(sys.argv[2],'w'),indent=1)
PY
L=runs/launch-$name.json; fi
start=$(date +%s)
( flock /dev/shm/card27.lock nice -n 10 taskset -c 8-15,24-31 python3 -B $D run --launch $L --out /dev/shm/ownrt-lab-r0/runs/$name --steps ${STEPS:-48} --prompt $prompt --rows $rows --cache /dev/shm/ownrt-lab-r0/cache > runs/$name.out 2>&1; echo $? > runs/$name.rc ) &
bg=$!
dri=""
for i in $(seq 1 900); do
  pid=$(pgrep -f -- "--output /dev/shm/ownrt-lab-r0/runs/$name/rank0" | head -1)
  if [ -n "$pid" ] && [ -e runs/$name/rank0/device-contact.json ]; then sleep 5; dri=$(ls -l /proc/$pid/fd 2>/dev/null | grep -o "/dev/dri/[a-zA-Z0-9]*" | sort -u | tr '\n' ' '); break; fi
  kill -0 $bg 2>/dev/null || break
  sleep 1
done
wait $bg
rc=$(cat runs/$name.rc)
echo "$dri" > runs/$name.dri
date +%s > last-check
if journalctl -k --since "@$start" --no-pager | grep -iE "$PAT"; then echo "KERNEL FAULT after $name"; touch HALT; exit 2; fi
[ "$rc" = "0" ] || { echo "RUN $name FAILED rc=$rc dri=[$dri]"; tail -5 runs/$name.out; tail -5 runs/$name/rank0.log 2>/dev/null; exit 1; }
python3 -c "
import json;s=json.load(open('runs/$name/summary.json'));m=lambda v:sorted(v)[len(v)//2]
print('$name prompt_ms',round(s['prompt_ms']),'replay_ms',round(s['draft_replay_ms']),'half_med',round(m(s['half_ms']),3),'draft_med',round(m(s['draft_ms']),3),'load_s',round(s['load_s'],1),'dri=[$dri]')"
grep -h "owned_bytes" runs/$name/rank0.log | head -2
