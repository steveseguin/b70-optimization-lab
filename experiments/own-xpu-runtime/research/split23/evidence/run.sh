#!/bin/bash
# run.sh NAME LAUNCH PROMPT ROWS [KEY=VALUE ...]: one rank-1 engine run on card 27 under the card lock, with the
# kernel-fault check before (since the previous check) and after (since this run's start). Any fault line -> HALT.
set -uo pipefail
cd /dev/shm/ownrt-lab-s23
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
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
( flock /dev/shm/card27.lock nice -n 10 taskset -c 8-15,24-31 python3 -B $D run --launch $L --out /dev/shm/ownrt-lab-s23/runs/$name --steps 48 --prompt $prompt --batched --rows $rows --cache /dev/shm/ownrt-lab-s23/cache > runs/$name.out 2>&1; echo $? > runs/$name.rc ) &
bg=$!
# record which DRM nodes the engine holds once it has loaded
dri=""
for i in $(seq 1 900); do
  pid=$(pgrep -f -- "--output /dev/shm/ownrt-lab-s23/runs/$name/rank1" | head -1)
  if [ -n "$pid" ] && [ -e runs/$name/rank1/device-contact.json ]; then sleep 5; dri=$(ls -l /proc/$pid/fd 2>/dev/null | grep -o "/dev/dri/[a-zA-Z0-9]*" | sort -u | tr '\n' ' '); break; fi
  kill -0 $bg 2>/dev/null || break
  sleep 1
done
wait $bg
rc=$(cat runs/$name.rc)
echo "$dri" > runs/$name.dri
date +%s > last-check
if journalctl -k --since "@$start" --no-pager | grep -iE "$PAT"; then echo "KERNEL FAULT after $name"; touch HALT; exit 2; fi
[ "$rc" = "0" ] || { echo "RUN $name FAILED rc=$rc dri=[$dri]"; tail -5 runs/$name.out; tail -5 runs/$name/rank1.log 2>/dev/null; exit 1; }
python3 -c "
import json;s=json.load(open('runs/$name/summary.json'));h=sorted(s['half_ms'])
print('$name prompt_ms',round(s['prompt_ms']),'half_med',round(h[len(h)//2],3),'load_s',round(s['load_s'],1),'dri=[$dri]')"
grep -h "owned_bytes" runs/$name/rank1.log | head -2
