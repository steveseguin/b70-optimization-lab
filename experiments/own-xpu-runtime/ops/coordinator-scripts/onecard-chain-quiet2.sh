#!/bin/bash
# onecard-chain-quiet2.sh <packet-dir-name> <orchestration-dir-name> [--check]
# Quiet-host variant (packet58ah chain-b preregistration, 2026-10-19): every Codex unit is frozen from BEFORE K1a
# (right before launch) until the chain ends, instead of from WS.
# Generic one-card record chain waiter (review 31): derives every path from the packet's own READY-FOR-DEVICE.json / ready.json /
# WINDOW.md, validates them in --check mode (no pauses, no launch), then: seal --verify + verify_ready, hold BOTH lanes,
# drain spacing, fresh fault review at the WINDOW.md path, hash-checked launch, freeze Codex from WS (watcher), release + thaw.
set -u
cd /home/steve/llm-optimizations
PK=$1; OR=$2; MODE=${3:-run}
L=experiments/own-xpu-runtime/ops/lane-queue; C=/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1; V3=experiments/own-xpu-runtime/stage2/screen/v3
P=experiments/own-xpu-runtime/stage2/$PK; O=experiments/own-xpu-runtime/ops/$OR; LOG=/tmp/claude-1000/-home-steve/fn-run/p58k.log
log(){ echo "$(date -u +%T) onecard-chain-quiet2[$PK] $*" >> $LOG; [ "$MODE" = --check ] && echo "$*"; }
cpu(){ nice -n 19 taskset -c 8-15,24-31 python3 -B "$@" </dev/null; }
fail(){ log "CHECK/ALERT: $*"; [ "$MODE" = --check ] || rm -f $L/PAUSE-A $L/PAUSE-B; exit 6; }
R=$O/READY-FOR-DEVICE.json
[ -s $R ] || fail "missing $R"
UNIT=$(python3 -c "import json;print(json.load(open('$R'))['coordinator_unit'])" 2>/dev/null) || fail "READY lacks coordinator_unit"
OUT=$(python3 -c "import json;print(json.load(open('$R'))['chain_output'])" 2>/dev/null) || fail "READY lacks chain_output"
WANT=$(python3 -c "import json;d=json.load(open('$R'));print(d.get('chain_command_digest_sha256') or d.get('chain_command_sha256') or '')")
FR=$(grep -o 'evidence/fault-review-[A-Za-z0-9_-]*\.json' $P/WINDOW.md | head -1); [ -n "$FR" ] || fail "WINDOW.md names no fault-review path"
for f in seal.py verify_ready.py fault_review.py; do [ -f $P/$f ] || fail "missing $P/$f"; done
[ -e "$OUT" ] && fail "chain output already exists: $OUT"
[ -n "$WANT" ] || fail "READY has no command digest"
log "derived: unit=$UNIT output=$OUT fault_review=$P/$FR"
if [ "$MODE" = --check ]; then
  cpu $P/seal.py --verify >/dev/null 2>&1 && echo "seal verify: ok" || echo "seal verify: FAILED"
  echo "check complete (no pause, no launch)"; exit 0; fi
for x in A B; do echo "held for $PK one-card record chain (whole host; coordinator $(date -u +%FT%TZ))" > $L/PAUSE-$x; done
(cpu $P/seal.py --verify && cpu $P/verify_ready.py --output $P/ready.json) >> $LOG 2>&1
r=$(python3 -c "import json;d=json.load(open('$P/ready.json'));print(d.get('ready'),'|',str(d.get('reason'))[:300])" 2>&1); log "ready: $r"
case "$r" in True*) ;; *) fail "not ready";; esac
cmd=$(python3 -c "import json;print(json.load(open('$P/ready.json'))['chain_command'])"); got=$(printf '%s' "$cmd" | sha256sum | cut -d' ' -f1)
[ "$WANT" = "$got" ] || fail "chain_command hash differs from READY"
case "$cmd" in *"--unit=$UNIT "*) ;; *) fail "chain_command unit differs from READY";; esac
while [ -e $L/inflight-A.json ] || [ -e $L/inflight-B.json ] || [ -e $C/active-lane-A.json ] || [ -e $C/active-lane-B.json ]; do sleep 10; done
python3 - <<'PY' >> $LOG 2>&1
import json,time
try: d=json.load(open('/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v3/teardown-state.json'))
except FileNotFoundError: d={}
if d.get('drained') and d.get('completed_monotonic'):
    w=d['completed_monotonic']+61.0-time.monotonic()
    if w>0: print('drain spacing wait',round(w,1)); time.sleep(w)
PY
cpu $P/fault_review.py --output $P/$FR >> $LOG 2>&1 || fail "fault review refused"
F=""; for u in $(systemctl --user list-units --state=active --no-legend 'codex-*' | awk '{print $1}'); do systemctl --user freeze $u && F="$F $u"; done; log "quiet host: codex frozen before K1a:$F"
systemctl --user reset-failed $UNIT 2>/dev/null; log "launching $UNIT"; eval "$cmd" >> $LOG 2>&1; log "systemd-run rc=$?"
seen=""; dl=$(( $(date +%s) + 3*3600 ))
while :; do s=$(systemctl --user is-active $UNIT 2>/dev/null); [ "$s" = active ] && seen=1; [ -n "$seen" ] && [ "$s" != active ] && [ "$s" != activating ] && break; [ -z "$seen" ] && [ "$s" = failed ] && break; [ $(date +%s) -gt $dl ] && { for u in $(systemctl --user list-units --no-legend 'codex-*' | sed 's/^●//' | awk '{print $1}'); do systemctl --user thaw $u 2>/dev/null; done; log "ALERT chain deadline; codex thawed; PAUSE-A/B kept (fault-halt)"; exit 9; }; sleep 20; done
log "$UNIT ended: $s"; sleep 30
for u in $(systemctl --user list-units --no-legend 'codex-*' | sed 's/^●//' | awk '{print $1}'); do systemctl --user thaw $u 2>/dev/null; done; log "codex thawed"
dr=$(python3 -c "import json;print(json.load(open('$V3/teardown-state.json')).get('drained'))" 2>/dev/null || echo True)
if [ -e $C/active-lane-A.json ] || [ -e $C/active-lane-B.json ] || [ "$dr" != True ] || ls $V3/fault-*.json >/dev/null 2>&1; then log "ALERT chain ended but marker/latch/undrained present; pauses kept"; exit 8; fi
rm -f $L/PAUSE-A $L/PAUSE-B; log "clean; pauses removed; coordinator prepares the submission"
