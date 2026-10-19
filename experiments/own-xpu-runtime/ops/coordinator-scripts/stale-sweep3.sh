#!/bin/bash
# Review 30 rec 3: archive dead-owner coordination artifacts within ~2 min, only if: owner pid dead for >= 60 s, GPU fault count still == base (2),
# lane flock free, lane render nodes idle. Any fault-count change => HALT (log and exit, archive nothing).
R=/home/steve/llm-optimizations/experiments/own-xpu-runtime; C=/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1; V3=$R/stage2/screen/v3
LOG=/tmp/claude-1000/-home-steve/fn-run/p118-chain.log; BASE=2; declare -A first
log(){ echo "$(date -u +%T) stale-sweep3 $*" >> $LOG; }
faults(){ (cd $R/stage1/packet4-prep/driver && python3 -B -c "import subprocess,window_driver as w;L=subprocess.run(['journalctl','-k','-b','--no-pager'],capture_output=True,text=True).stdout.splitlines();print(sum(1 for x in L if w.FAULT.search(x) and not w.DELETED.search(x)))"); }
pidof_json(){ python3 -c "import json,sys;d=json.load(open(sys.argv[1]));p=d.get('pid');print(p if isinstance(p,int) else '')" "$1" 2>/dev/null; }
lane_idle(){ local lane=$1 pre; [ "$lane" = A ] && pre='0000:2' || pre='0000:4'; flock -n $C/lane-$lane.lock true || return 1
  for n in /dev/dri/by-path/pci-${pre}*-render; do [ "$(fuser $(readlink -f $n) 2>/dev/null | wc -w)" = 0 ] || return 1; done; return 0; }
consider(){ local f=$1 lane=$2 p; [ -f "$f" ] || { unset first[$f]; return; }; p=$(pidof_json "$f")
  if [ -n "$p" ] && [ -d /proc/$p ]; then unset first[$f]; return; fi
  [ -n "${first[$f]}" ] || { first[$f]=$(date +%s); return; }; [ $(( $(date +%s) - ${first[$f]} )) -ge 60 ] || return
  fc=$(faults); [ "$fc" = "$BASE" ] || { log "HALT: fault count $fc != $BASE; nothing archived"; exit 9; }
  if [ -n "$lane" ]; then lane_idle $lane || return; else lane_idle A && lane_idle B || return; fi
  tag=$(basename $(dirname "$f"))-$(basename "$f" .json)-$(date -u +%Y%m%dT%H%M%SZ)
  flock -w 10 $C/protocol.lock -c "[ -f '$f' ] && cp '$f' '$C/reviewed/sweep-$tag.json' && rm '$f'" && log "archived $f (owner pid ${p:-none} dead >=60s, faults $fc, lane ${lane:-A+B} idle)"; unset first[$f]; }
while :; do
  consider $C/active-lane-A.json A; consider $C/active-lane-B.json B; consider $C/hold-lane-B ""
  if [ -f $V3/teardown-state.json ] && python3 -c "import json,sys;sys.exit(0 if json.load(open('$V3/teardown-state.json')).get('drained') is False else 1)" 2>/dev/null; then consider $V3/teardown-state.json ""; fi
  for x in $V3/fault-*-A.json; do [ -f "$x" ] && consider "$x" A; done; for x in $V3/fault-*-B.json; do [ -f "$x" ] && consider "$x" B; done
  # packet-local latches: only recent (< 3 h), untracked, top-level fault-<current boot>.json files
  boot=$(cat /proc/sys/kernel/random/boot_id)
  for x in $(find $R/stage2 -maxdepth 3 \( -path "*/stage2/packet*/fault-$boot.json" -o -path "*/stage2/packet*/screen/fault-$boot.json" \) -name "fault-$boot.json" -mmin -180 2>/dev/null); do git -C /home/steve/llm-optimizations ls-files --error-unmatch "$x" >/dev/null 2>&1 && continue; consider "$x" ""; done
  sleep 20; done
