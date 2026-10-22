#!/bin/bash
# p182-win.sh — packet182 win-path chain waiter. PREPARED, NOT ARMED (arming: chain/ARMING.md).
# Armed by the device-window driver BEFORE packet182-one-card-v5-A starts. It never queues, never
# deletes a PAUSE file, never restarts anything, never retries, and never touches a service.
#  1. wait for the v5 job's terminal event in events-A.jsonl (deadline 3 h; the v5 takes ~13-14 min);
#  2. chain rule (chain/chain_gate.py): v5 passed, 60/60 exact, drift <= 3%, min gain >= +2%,
#     slower B >= 1.02 x the live one-card record threshold; otherwise stop (NOCHAIN is a normal end);
#  3. derive packet182c-chain with chain/derive_chain.py (ops generator + fixed flag placement +
#     carried post-native rehearsal), then refuse unless chain/script_argv_check.py (script mode, every
#     model window carries --wait-policy spin --foreground-io kernel), --predevice-check and
#     --closure-check pass; --postnative-check is run and logged (it refuses without real chain
#     evidence on this host; the carry recorded in ops/packet182c-orchestration stands in);
#  4. refuse while any owner endpoint unit is active (card 0 / host memory), then one-card hold lock + QUIET,
#     then chain/p182-chain.sh (quiet chain launcher that keeps PAUSE files and re-checks the endpoints).
# The chain is 7 windows (K1a K1b KD W2m WS WS128x WS128), ~35 min (chain 176-a: 12:01:09-12:36:11Z).
set -u
cd "${P182_REPO:-/home/steve/llm-optimizations}"   # P182_REPO: CPU rehearsal root only (chain/rehearse_waiter.py)
X=experiments/own-xpu-runtime; L=$X/ops/lane-queue; P=$X/stage2/packet182-onecard-kio-rebracket
FN=${FN:-/tmp/claude-1000/-home-steve/fn-run}; export FN; LOG=${LOG:-$FN/p182-win.log}; export LOG; mkdir -p $FN
log(){ echo "$(date -u +%FT%TZ) p182-win $*" >> $LOG; }
cpu(){ nice -n 19 taskset -c 8-15,24-31 python3 -B "$@" </dev/null; }
JOB=packet182-one-card-v5-A
S=$P/screen/evidence/card0-182-v5-a/resident/WSCREEN/summary.json
CH=$X/stage2/packet182c-chain
log "armed: waiting for $JOB"
dl=$(( $(date +%s) + 3*3600 ))
until grep "\"name\": \"$JOB\"" $L/events-A.jsonl 2>/dev/null | grep -qE '"event": "(DONE|FAILED|REFUSED|REFUSED-fast|REPORT-FAILED|REFUSED-PREDEVICE|SKIPPED-DEPENDENCY)"'; do
  [ $(date +%s) -gt $dl ] && { log "deadline: no terminal event for $JOB in 3 h; no chain"; exit 3; }; sleep 15; done
grep "\"name\": \"$JOB\"" $L/events-A.jsonl | grep -q '"event": "DONE"' || { log "$JOB did not end DONE; no chain"; exit 2; }
sleep 30
[ -s $S ] || { log "no bracket summary at $S; no chain"; exit 2; }
W=$(cpu $P/chain/chain_gate.py $S 2>&1); log "bracket: $W"
case "$W" in CHAIN*) ;; *) log "no chain (chain rule not met); bracket evidence kept for the readout"; exit 0;; esac
# The owner's daily endpoints (card 0 = qwen38-27b-fp8) must still be stopped: a window driver that restores
# them after the last queue row would collide with the chain on card 0 and the whole-host memory floor.
EP=${P182_ENDPOINT_UNITS:-"qwen38-27b-fp8 qwen38-27b-fp8-tp1-test qwen38-27b-vision"}
for u in $EP; do s=$(systemctl --user is-active $u 2>/dev/null); case "$s" in active|activating|reloading|deactivating) log "ALERT endpoint $u is $s; no chain (driver must wait for p182-win before restoring endpoints)"; exit 5;; esac; done
[ -e $CH ] && { log "ALERT $CH already exists; no chain (never reuse a derived packet)"; exit 4; }
cpu $P/chain/derive_chain.py --parent-orch $X/ops/packet58aj-orchestration --packet $CH --out $X/ops/packet182c-orchestration \
  --unit packet58-onecard-182-a --output evidence/card0-182-a --binary $P/build/device/own-rt-iq3 --host-binary $P/build/gnu-host/own-rt-iq3 \
  --bracket-summary $S --threshold-file scripts/packet58_onecard_record_threshold.json --flag wait-policy=spin --flag foreground-io=kernel >> $LOG 2>&1 \
  || { log "ALERT derive refused (see log above); no chain"; exit 4; }
cpu $P/chain/script_argv_check.py $CH --json $CH/evidence/script-argv-check.json >> $LOG 2>&1 || { log "ALERT script-mode argv lacks a chain flag; no chain"; exit 4; }
cpu $X/ops/onecard_chain_derive.py --predevice-check $CH >> $LOG 2>&1 || { log "ALERT --predevice-check refused; no chain"; exit 4; }
cpu $X/ops/onecard_chain_derive.py --closure-check $CH >> $LOG 2>&1 || { log "ALERT --closure-check refused; no chain"; exit 4; }
if cpu $X/ops/onecard_chain_derive.py --postnative-check $CH >> $LOG 2>&1; then log "--postnative-check passed on real chain evidence"
else log "--postnative-check: no completed one-card chain evidence on this host (expected); carried packet176c rehearsal in ops/packet182c-orchestration/postnative-rehearsal.json"; fi
out=$(bash $P/chain/p182-chain.sh packet182c-chain packet182c-orchestration --check 2>&1)
echo "$out" | grep -q "seal verify: ok" && echo "$out" | grep -q "check complete" || { log "ALERT chain --check failed: $(echo "$out" | tail -2 | tr '\n' ' ' | cut -c1-200)"; exit 4; }
if [ "${P182_DRY_RUN:-0}" = 1 ]; then log "dry run: derive, checks and chain --check passed; would take onecard-hold.lock, set QUIET and run p182-chain.sh"; exit 0; fi
exec 9>$FN/onecard-hold.lock; flock -w 7200 9 || { log "deadline onecard lock"; exit 3; }
echo "record chain 182-a $(date -u +%FT%TZ)" > $FN/QUIET; log "derive + checks ok; QUIET set; launching quiet chain"
bash $P/chain/p182-chain.sh packet182c-chain packet182c-orchestration; rc=$?
rm -f $FN/QUIET; log "chain exited rc=$rc; QUIET cleared"
exit $rc
