#!/bin/bash
# Quiet chain (full Codex freeze from before K1a). After codex-p58asc exits with a fresh READY (ready_for_device true): onecard-chain.sh --check, then the real chain.
cd /home/steve/llm-optimizations
LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log; log(){ echo "$(date -u +%T) chain-58as $*" >> $LOG; }
R=experiments/own-xpu-runtime/ops/packet58as-orchestration/READY-FOR-DEVICE.json; T0=$(date -d "2026-10-19 08:52:50 UTC" +%s); dl=$(( $(date +%s) + 5400 ))
while systemctl --user list-units --state=active --no-legend "codex-p58asc-*" | grep -q . ; do [ $(date +%s) -gt $dl ] && { log "deadline waiting for p58asc"; exit 3; }; sleep 20; done; sleep 10
[ -s $R ] && [ $(stat -c %Y $R) -gt $T0 ] || { log "no fresh orchestration READY; no chain"; exit 2; }
python3 -c "import json,sys;d=json.load(open('$R'));sys.exit(0 if d.get('ready_for_device') is True and d.get('coordinator_unit') and d.get('chain_output') else 1)" || { log "READY not ready / incomplete; no chain"; exit 2; }
out=$(bash /tmp/claude-1000/-home-steve/fn-run/onecard-chain.sh packet58as-onecard-spinwait packet58as-orchestration --check 2>&1)
echo "$out" | grep -q "seal verify: ok" && echo "$out" | grep -q "check complete" || { log "ALERT --check failed: $(echo "$out" | tail -2 | tr '\n' ' ' | cut -c1-200)"; exit 4; }
exec 9>/tmp/claude-1000/-home-steve/fn-run/onecard-hold.lock; flock -w 7200 9 || { log "deadline onecard lock"; exit 3; }
log "check ok; launching quiet chain"
bash /tmp/claude-1000/-home-steve/fn-run/onecard-chain-quiet2.sh packet58as-onecard-spinwait packet58as-orchestration
log "chain waiter exited rc=$?"
