#!/bin/bash
# launch_chain.sh — packet195 k3x-diet record chain, guarded coordinator launcher (packet182 p182-win.sh pattern; packet187's launcher with the k3 host floor).
# PREPARED, NOT ARMED. Run by the coordinator once, by hand:
#   bash experiments/own-xpu-runtime/ops/packet195-orchestration/launch_chain.sh --dry-run   # all checks, no launch
#   bash experiments/own-xpu-runtime/ops/packet195-orchestration/launch_chain.sh             # checks, then launch
# It never queues, never deletes or creates a PAUSE file, never stops/starts/restarts an endpoint or service,
# never retries, and has a deadline on every wait. It launches only through the orchestration's own command:
# the exact `ready.json.chain_command` (systemd-run unit packet195-chain-a -> device-entry.sh ->
# coordinator_windows.sh -> chain_entry.py queue), after re-verifying it against verify_ready.py.
# Refuses unless:
#   1. all three owner endpoint units are inactive (qwen38-27b-fp8 card 0, qwen38-27b-fp8-tp1-test card 3,
#      qwen38-27b-vision cards 1+2) - the chain uses cards 0+1 and the whole-host memory floor;
#   2. PAUSE-B exists (kept for the whole chain) and PAUSE-A does not (the coordinator archives it for the chain);
#   3. no inflight-A/B.json lane marker, no active-lane-A/B.json coordination marker, no lanequeue-*,
#      window-* (other than the unit running this launcher) or packet195-chain-a unit active/activating,
#      and no earlier packet195-chain-a unit in any non-inactive state (failed attempts are never reset here);
#   4. MemAvailable >= 108,797,048,558 + 1,073,741,824 B (packet194/189 k3-storage host admission, unchanged by the diet, + the queue's 1 GiB);
#   5. root free >= 25 GB + the chain's planned writes (3,324,718,708 B);
#   6. the registered output build/device-cards01-p195-a does not exist;
#   7. verify_ready.py passes and its chain_command equals ready.json's.
# Expected chain wall time ~46-47 min (11 windows + 10 x 90 s gaps; packet136 chain 2026-10-18 16:55:53-17:42:05Z).
# After launch it returns once the unit is active: the coordinator watches packet195-chain-a and its output
# (README "Launch procedure"); restoring endpoints/PAUSE-A after the chain is the coordinator's decision.
set -u
cd /home/steve/llm-optimizations
X=experiments/own-xpu-runtime; O=$X/ops/packet195-orchestration; P=$X/stage2/packet195-record-bundle-diet
L=${P195_LANE_DIR:-$X/ops/lane-queue}   # P195_LANE_DIR: CPU rehearsal copy only (final_checks.py); default = the live lane-queue dir
MEMINFO=${P195_MEMINFO:-/proc/meminfo}  # P195_MEMINFO: CPU rehearsal only (final_checks.py); default = the live host
C=${P195_COORD_DIR:-/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1}  # P195_COORD_DIR: CPU rehearsal only
FN=${FN:-/tmp/claude-1000/-home-steve/fn-run}; mkdir -p "$FN"; LOG=$FN/p195-launch.log
DRY=0; [ "${1:-}" = --dry-run ] && DRY=1
[ $# -le 1 ] && { [ $# -eq 0 ] || [ $DRY = 1 ]; } || { echo "usage: $0 [--dry-run]"; exit 64; }
# Rehearsal overrides can never launch: with either override set, only --dry-run is accepted.
{ [ -n "${P195_LANE_DIR:-}" ] || [ -n "${P195_MEMINFO:-}" ] || [ -n "${P195_COORD_DIR:-}" ]; } && [ $DRY = 0 ] && { echo "rehearsal overrides require --dry-run"; exit 64; }
log(){ echo "$(date -u +%FT%TZ) p195-launch $*" | tee -a "$LOG"; }
cpu(){ timeout 1800 nice -n 19 taskset -c 8-15,24-31 python3 -B "$@" </dev/null; }
refuse(){ log "REFUSED: $*"; exit 4; }
for u in qwen38-27b-fp8 qwen38-27b-fp8-tp1-test qwen38-27b-vision; do
  s=$(timeout 30 systemctl --user is-active "$u" 2>/dev/null); case "$s" in active|activating|reloading|deactivating) refuse "owner endpoint $u is $s (stop all three endpoints first)";; esac
done
[ -e "$L/PAUSE-B" ] || refuse "PAUSE-B is absent: it must stay in place for the whole chain"
[ -e "$L/PAUSE-A" ] && refuse "PAUSE-A is present: archive it for the chain first (this launcher never touches PAUSE files)"
for m in "$L/inflight-A.json" "$L/inflight-B.json" "$C/active-lane-A.json" "$C/active-lane-B.json"; do
  [ -e "$m" ] && refuse "lane marker $m exists (a lane job is in flight or left its marker; resolve it first)"; done
# The unit this launcher itself runs in (e.g. a coordinator window-p195-* driver) is not a competitor.
SELF=$(awk -F/ '/^0::/{print $NF}' /proc/self/cgroup 2>/dev/null)
busy=$(timeout 30 systemctl --user list-units --no-legend --plain --state=active,activating 'lanequeue-*' 'window-*' 'packet195-chain-a*' 2>/dev/null | awk -v self="$SELF" '$1 != self {print $1}' | tr '\n' ' ')
[ -n "$busy" ] && refuse "active lane/window/chain units: $busy"
s=$(timeout 30 systemctl --user is-active packet195-chain-a 2>/dev/null); case "$s" in inactive|unknown|"") ;; *) refuse "unit packet195-chain-a is $s (a previous attempt exists: inspect it; never reset or retry automatically)";; esac
avail=$(awk '/^MemAvailable:/{print $2*1024}' "$MEMINFO"); need=$((108797048558 + 1073741824))
[ -n "$avail" ] && [ "$avail" -ge "$need" ] || refuse "MemAvailable ${avail:-unreadable} < $need"
free=$(df -B1 --output=avail / | tail -1); [ "$free" -ge $((25000000000 + 3324718708)) ] || refuse "root free $free below 25 GB + planned writes"
OUT=/home/steve/llm-optimizations/$P/build/device-cards01-p195-a
[ -e "$OUT" ] && refuse "$OUT exists: the registered chain output must be fresh (never reuse)"
V=$(cpu $O/verify_ready.py 2>&1) || refuse "verify_ready.py failed: $(echo "$V" | tail -2 | tr '\n' ' ' | cut -c1-300)"
CMD=$(cpu -c "import json;print(json.load(open('$O/ready.json'))['chain_command'])") || refuse "ready.json unreadable"
LIVE=$(echo "$V" | python3 -c "import json,sys;print(json.load(sys.stdin)['chain_command'])") || refuse "verify_ready output unreadable"
[ "$CMD" = "$LIVE" ] || refuse "ready.json chain_command differs from the verified command"
case "$CMD" in "systemd-run --user --unit=packet195-chain-a "*" $O/device-entry.sh chain $OUT </dev/null"|"systemd-run --user --unit=packet195-chain-a "*"/home/steve/llm-optimizations/$O/device-entry.sh chain $OUT </dev/null") ;; *) refuse "unexpected chain command";; esac
if [ $DRY = 1 ]; then log "dry run: every check passed; would run: $CMD"; exit 0; fi
log "all checks passed; launching: $CMD"
bash -c "$CMD" >> "$LOG" 2>&1 || refuse "systemd-run returned non-zero (no retry)"
dl=$(( $(date +%s) + 120 ))
until s=$(timeout 30 systemctl --user is-active packet195-chain-a 2>/dev/null); [ "$s" = active ] || [ "$s" = failed ] || [ "$s" = inactive ]; do
  [ $(date +%s) -gt $dl ] && { log "deadline: packet195-chain-a not active within 120 s (state $s); inspect the unit, no retry"; exit 3; }; sleep 5; done
log "packet195-chain-a is $s; chain owns its windows now (no retry, no service restoration by this launcher)"
[ "$s" = active ] || exit 2
exit 0
