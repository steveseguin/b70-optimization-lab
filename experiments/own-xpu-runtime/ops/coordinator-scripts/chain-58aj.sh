#!/bin/bash
# After codex-p58ajc exits with a fresh READY (ready_for_device true): onecard-chain.sh --check, then the real chain.
cd /home/steve/llm-optimizations
LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log; log(){ echo "$(date -u +%T) chain-58aj $*" >> $LOG; }
R=experiments/own-xpu-runtime/ops/packet58aj-orchestration/READY-FOR-DEVICE.json; T0=$(date -d "2026-10-19 03:33:54 UTC" +%s); dl=$(( $(date +%s) + 3600 ))
while systemctl --user list-units --state=active --no-legend "codex-p58ajc-*" | grep -q . ; do [ $(date +%s) -gt $dl ] && { log "deadline waiting for p58ajc"; exit 3; }; sleep 20; done; sleep 10
[ -s $R ] && [ $(stat -c %Y $R) -gt $T0 ] || { log "no fresh orchestration READY; no chain"; exit 2; }
python3 -c "import json,sys;d=json.load(open('$R'));sys.exit(0 if d.get('ready_for_device') is True and d.get('coordinator_unit') and d.get('chain_output') else 1)" || { log "READY not ready / incomplete; no chain"; exit 2; }
out=$(bash /tmp/claude-1000/-home-steve/fn-run/onecard-chain.sh packet58aj-onecard-resident packet58aj-orchestration --check 2>&1)
echo "$out" | grep -q "seal verify: ok" && echo "$out" | grep -q "check complete" || { log "ALERT --check failed: $(echo "$out" | tail -2 | tr '\n' ' ' | cut -c1-200)"; exit 4; }
log "check ok; launching chain"
bash /tmp/claude-1000/-home-steve/fn-run/onecard-chain.sh packet58aj-onecard-resident packet58aj-orchestration
log "chain waiter exited rc=$?"
