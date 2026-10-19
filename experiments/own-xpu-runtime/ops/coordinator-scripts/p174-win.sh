#!/bin/bash
# p174-win.sh (review 44 rec 2): on packet174-v5-A DONE, read the bracket; on a win derive the chain with
# ops/onecard_chain_derive.py (fail-closed), --check it, and launch the quiet chain under QUIET + onecard-hold.lock.
cd /home/steve/llm-optimizations; FN=/tmp/claude-1000/-home-steve/fn-run; LOG=$FN/p58k.log; log(){ echo "$(date -u +%T) p174-win $*" >> $LOG; }
X=experiments/own-xpu-runtime; L=$X/ops/lane-queue; P=$X/stage2/packet174-onecard-fillkick; dl=$(( $(date +%s) + 3*3600 ))
until grep '"name": "packet174-v5-A"' $L/events-A.jsonl | grep -qE '"event": "(DONE|FAILED|REFUSED|REFUSED-fast|REPORT-FAILED|REFUSED-PREDEVICE)'; do [ $(date +%s) -gt $dl ] && { log deadline; exit 3; }; sleep 15; done
grep '"name": "packet174-v5-A"' $L/events-A.jsonl | grep -q '"event": "DONE"' || { log "p174 did not finish DONE; no chain"; exit 2; }
sleep 30; S=$(find $P/screen/evidence -path '*WSCREEN/summary.json' -not -path '*/run/*' 2>/dev/null | head -1)
W=$(python3 -c "import json;d=json.load(open('$S'));print('WIN' if d.get('candidate_beats_all_controls') is True and d.get('passed') is True else 'LOSS', d.get('rates'), round(d.get('minimum_gain_vs_best_control',0)*100,3))" 2>&1); log "bracket: $W"
case "$W" in WIN*) ;; *) log "no chain (loss or unreadable)"; exit 0;; esac
for i in $(seq 1 60); do git log --oneline -20 | grep -qi "generator\|derive\|packet172" && grep -q "prefix" $X/ops/onecard_chain_derive.py && break; sleep 30; done
nice -n 19 taskset -c 8-15,24-31 python3 -B $X/ops/onecard_chain_derive.py --parent-orch $X/ops/packet58aj-orchestration --packet $X/stage2/packet174c-chain --out $X/ops/packet174c-orchestration --unit packet58-onecard-174-a --output evidence/card0-174-a --binary $P/build/device/own-rt-iq3 --host-binary $P/build/gnu-host/own-rt-iq3 --bracket-summary $S --threshold-file scripts/packet58_onecard_record_threshold.json --flag wait-policy=spin --flag fill-kick=on </dev/null > $FN/p174-derive.log 2>&1 || { log "ALERT derive failed: $(tail -c 300 $FN/p174-derive.log | tr '\n' ' ')"; exit 4; }
out=$(bash $FN/onecard-chain.sh packet174c-chain packet174c-orchestration --check 2>&1)
echo "$out" | grep -q "seal verify: ok" && echo "$out" | grep -q "check complete" || { log "ALERT --check failed: $(echo "$out" | tail -2 | tr '\n' ' ' | cut -c1-200)"; exit 4; }
exec 9>$FN/onecard-hold.lock; flock -w 7200 9 || { log "deadline onecard lock"; exit 3; }
echo "chain 174-a $(date -u +%FT%TZ)" > $FN/QUIET; log "derive + check ok; QUIET set; launching quiet chain"
bash $FN/onecard-chain-quiet2.sh packet174c-chain packet174c-orchestration; rc=$?; rm -f $FN/QUIET; log "chain exited rc=$rc; QUIET cleared"
