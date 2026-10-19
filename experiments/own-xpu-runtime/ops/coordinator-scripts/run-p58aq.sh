#!/bin/bash
cd /home/steve/llm-optimizations; LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log; log(){ echo "$(date -u +%T) run-p58aq $*" >> $LOG; }
L=experiments/own-xpu-runtime/ops/lane-queue
nm(){ python3 -c "import json;print([json.loads(l)['name'] for l in open('$L/$1') if l.strip() and not l.startswith('#')][0])"; }
SM=$(nm proposed-p58aq-smoke-A.txt); SP=$(nm proposed-p58aq-split-A.txt)
t=$(( $(date +%s) + 180 )); while ls /home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1/active-lane-*.json >/dev/null 2>&1; do [ $(date +%s) -gt $t ] && { log "marker present; not starting"; exit 3; }; sleep 10; done
log "smoke $SM"; bash /tmp/claude-1000/-home-steve/fn-run/hold-single.sh proposed-p58aq-smoke-A.txt $SM
grep "hold-single\[$SM\] $SM:" $LOG | tail -1 | grep -q '"DONE"' || { log "smoke did not pass; no diagnostic"; exit 5; }
sleep 30; t=$(( $(date +%s) + 300 )); while ls /home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1/active-lane-*.json >/dev/null 2>&1; do [ $(date +%s) -gt $t ] && { log "marker present after smoke"; exit 3; }; sleep 10; done
systemctl --user list-units --state=active --no-legend "lanequeue-A*" | grep -q . || { log "no lane-A driver"; exit 4; }
F=""; for u in $(systemctl --user list-units --state=active --no-legend 'codex-*' | awk '{print $1}'); do systemctl --user freeze $u && F="$F $u"; done; log "codex frozen for diagnostic:$F"
bash /tmp/claude-1000/-home-steve/fn-run/hold-single.sh proposed-p58aq-split-A.txt $SP
for u in $(systemctl --user list-units --no-legend 'codex-*' | sed 's/^●//' | awk '{print $1}'); do systemctl --user thaw $u 2>/dev/null; done; log "codex thawed; diagnostic: $(grep "hold-single\[$SP\] $SP:" $LOG | tail -1 | grep -oE '"event": "[A-Z-]+"')"
