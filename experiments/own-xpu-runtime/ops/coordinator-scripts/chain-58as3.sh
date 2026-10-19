#!/bin/bash
# Launch the packet58as quiet record chain once the orchestration READY is true (finished by a Claude subagent; Codex is out).
# Creates fn-run/QUIET for the chain's duration (subagents pause compiles/heavy CPU while it exists), takes the one-card lock.
cd /home/steve/llm-optimizations; FN=/tmp/claude-1000/-home-steve/fn-run; LOG=$FN/p58k.log; log(){ echo "$(date -u +%T) chain-58as3 $*" >> $LOG; }
R=experiments/own-xpu-runtime/ops/packet58as-orchestration/READY-FOR-DEVICE.json
python3 -c "import json,sys;d=json.load(open('$R'));sys.exit(0 if d.get('ready_for_device') is True and d.get('coordinator_unit') and d.get('chain_output') else 1)" || { log "READY not ready / incomplete; no chain"; exit 2; }
out=$(bash $FN/onecard-chain.sh packet58as-onecard-spinwait packet58as-orchestration --check 2>&1)
echo "$out" | grep -q "seal verify: ok" && echo "$out" | grep -q "check complete" || { log "ALERT --check failed: $(echo "$out" | tail -2 | tr '\n' ' ' | cut -c1-200)"; exit 4; }
exec 9>$FN/onecard-hold.lock; flock -w 7200 9 || { log "deadline onecard lock"; exit 3; }
echo "chain 58as-a $(date -u +%FT%TZ)" > $FN/QUIET; log "check ok; QUIET set; launching quiet chain"
bash $FN/onecard-chain-quiet2.sh packet58as-onecard-spinwait packet58as-orchestration; rc=$?
rm -f $FN/QUIET; log "chain waiter exited rc=$rc; QUIET cleared"
