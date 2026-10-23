#!/bin/bash
# launch_chain.sh — packet58-onecard-cache23-chain one-card record chain, guarded coordinator launcher
# (packet190 launch_chain.sh pattern + the packet182 p182-chain.sh checks: seal/verify_ready, command digest, fresh fault review,
# drain spacing, quiet host). PREPARED, NOT ARMED. Run by the coordinator once, by hand, from the repository root:
#   bash experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/launch_chain.sh --dry-run   # every check, no launch
#   bash experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/launch_chain.sh             # checks, fresh fault review, launch
# It never queues, never creates/deletes/edits a PAUSE or STOP file, never starts/stops/freezes/restarts any unit or endpoint,
# never retries, and has a deadline on every wait. It launches only the exact `ready.json.chain_command` of the packet
# (systemd-run --user --unit=packet58-onecard-cache23-a ... queue_runner.py --authorized-device-window ...), after re-running
# the packet's seal.py --verify and verify_ready.py and comparing the command digest with READY-FOR-DEVICE.json.
# Refuses (rc 4) unless:
#   1. the three owner endpoint units are inactive (qwen38-27b-fp8 card 0, qwen38-27b-fp8-tp1-test card 3, qwen38-27b-vision cards 1+2):
#      the chain owns card 0 and the whole-host memory floor;
#   2. PAUSE-B exists (kept for the whole chain) and PAUSE-A does not (the coordinator archives it for the chain; never this script);
#   3. no inflight-A/B.json lane marker, no active-lane-A/B.json coordination marker, no lanequeue-*, window-* (other than the unit
#      running this launcher) or packet58-onecard-cache23-a unit active/activating, no earlier packet58-onecard-cache23-a unit in any
#      non-inactive state (a failed attempt is never reset here), no active codex-* unit that is not frozen (quiet host);
#   4. MemAvailable >= 100,487,123,456 + 1,073,741,824 B (the cache23 host admission + the queue's 1 GiB);
#   5. root free >= 25 GB + the chain's planned writes (397,492,208 B: window.WRITES of the 7 windows);
#   6. no process holds a /dev/dri render node (read-only /proc scan);
#   7. the registered output evidence/card0-cache23-a and the fault review evidence/fault-review-cache23-a.json do not exist;
#   8. READY-FOR-DEVICE.json is the final one (final_checks_sha256), seal.py --verify and verify_ready.py pass, the command digest
#      equals READY's, and the command has the expected shape;
#   9. the fault review (exactly two known fault lines on this boot) captures cleanly: in --dry-run to a temporary evidence file that is
#      removed; in a real run to evidence/fault-review-cache23-a.json immediately before launch.
# Expected chain wall time ~35 min (7 windows + 6 x 90 s gaps; packet182c chain 2026-10-22 09:47:31-10:20:52Z).
# After launch it returns once the unit is active; the coordinator watches packet58-onecard-cache23-a and its output (README).
set -u
cd /home/steve/llm-optimizations
X=experiments/own-xpu-runtime; O=$X/ops/packet58c23chain-orchestration; P=$X/stage2/packet58-onecard-cache23-chain
L=${P58C23_LANE_DIR:-$X/ops/lane-queue}   # rehearsal override only (final_checks.py); default = the live lane-queue dir
MEMINFO=${P58C23_MEMINFO:-/proc/meminfo}  # rehearsal override only
C=${P58C23_COORD_DIR:-/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1}  # rehearsal override only
PROC=${P58C23_PROC:-/proc}               # rehearsal override only (render-node scan)
FN=${FN:-/tmp/claude-1000/-home-steve/fn-run}; mkdir -p "$FN"; LOG=$FN/p58c23-launch.log
UNIT=packet58-onecard-cache23-a
DRY=0; [ "${1:-}" = --dry-run ] && DRY=1
[ $# -le 1 ] && { [ $# -eq 0 ] || [ $DRY = 1 ]; } || { echo "usage: $0 [--dry-run]"; exit 64; }
{ [ -n "${P58C23_LANE_DIR:-}" ] || [ -n "${P58C23_MEMINFO:-}" ] || [ -n "${P58C23_COORD_DIR:-}" ] || [ -n "${P58C23_PROC:-}" ]; } && [ $DRY = 0 ] && { echo "rehearsal overrides require --dry-run"; exit 64; }
log(){ echo "$(date -u +%FT%TZ) p58c23-launch $*" | tee -a "$LOG"; }
cpu(){ timeout 1800 nice -n 19 taskset -c 8-15,24-31 python3 -B "$@" </dev/null; }
refuse(){ log "REFUSED: $*"; exit 4; }
for u in qwen38-27b-fp8 qwen38-27b-fp8-tp1-test qwen38-27b-vision; do
  s=$(timeout 30 systemctl --user is-active "$u" 2>/dev/null); case "$s" in active|activating|reloading|deactivating) refuse "owner endpoint $u is $s (stop all three endpoints first; this script never stops a unit)";; esac
done
[ -e "$L/PAUSE-B" ] || refuse "PAUSE-B is absent: it must stay in place for the whole chain"
[ -e "$L/PAUSE-A" ] && refuse "PAUSE-A is present: archive it for the chain first (this launcher never touches PAUSE files)"
for m in "$L/inflight-A.json" "$L/inflight-B.json" "$C/active-lane-A.json" "$C/active-lane-B.json"; do
  [ -e "$m" ] && refuse "lane marker $m exists (a lane job is in flight or left its marker; resolve it first)"; done
SELF=$(awk -F/ '/^0::/{print $NF}' /proc/self/cgroup 2>/dev/null)
busy=$(timeout 30 systemctl --user list-units --no-legend --plain --state=active,activating 'lanequeue-*' 'window-*' "$UNIT*" 2>/dev/null | awk -v self="$SELF" '$1 != self {print $1}' | tr '\n' ' ')
[ -n "$busy" ] && refuse "active lane/window/chain units: $busy"
s=$(timeout 30 systemctl --user is-active "$UNIT" 2>/dev/null); case "$s" in inactive|unknown|"") ;; *) refuse "unit $UNIT is $s (a previous attempt exists: inspect it; never reset or retry automatically)";; esac
for u in $(timeout 30 systemctl --user list-units --no-legend --plain --state=active 'codex-*' 2>/dev/null | awk '{print $1}'); do
  f=$(timeout 30 systemctl --user show -p FreezerState --value "$u" 2>/dev/null); [ "$f" = frozen ] || refuse "codex unit $u is active and not frozen (quiet host: freeze or stop codex-* first; this script never freezes a unit)"
done
avail=$(awk '/^MemAvailable:/{print $2*1024}' "$MEMINFO"); need=$((100487123456 + 1073741824))
[ -n "$avail" ] && [ "$avail" -ge "$need" ] || refuse "MemAvailable ${avail:-unreadable} < $need"
writes=$(cpu -c "import json;print(json.load(open('$P/evidence/launch-limits.json'))['planned_write_bytes'])") || refuse "launch-limits receipt unreadable"
[ "$writes" = 397492208 ] || refuse "planned writes $writes differ from the sealed 397,492,208"
free=$(df -B1 --output=avail / | tail -1); [ "$free" -ge $((25000000000 + writes)) ] || refuse "root free $free below 25 GB + planned writes $writes"
users=""; for p in "$PROC"/[0-9]*; do [ "$(basename "$p")" = "$$" ] && continue; ls -l "$p/fd" 2>/dev/null | grep -q '/dev/dri/' && users="$users $(basename "$p")"; done
[ -n "$users" ] && refuse "render-node users present (pids:$users); the chain needs every /dev/dri client gone"
OUT=/home/steve/llm-optimizations/$P/evidence/card0-cache23-a; FR=/home/steve/llm-optimizations/$P/evidence/fault-review-cache23-a.json
[ -e "$OUT" ] && refuse "$OUT exists: the registered chain output must be fresh (never reuse, never retry)"
[ -e "$FR" ] && refuse "$FR exists: the fault review must be captured fresh by this launcher"
R=$P/READY-FOR-DEVICE.json; [ -s "$R" ] || refuse "missing $R"
python3 -c "import json;d=json.load(open('$R'));assert d['ready_for_device_chain'] is True and d['passed'] is True and d.get('final_checks_sha256') and d['last_packet_write'] is True" 2>/dev/null || refuse "READY is not the final one (final_checks.py --ready writes it last)"
WANT=$(python3 -c "import json;print(json.load(open('$R'))['chain_command_digest_sha256'])")
cpu "$P/seal.py" --verify >/dev/null 2>&1 || refuse "seal.py --verify failed"
V=$(cpu "$O/verify_ready.py" 2>&1) || refuse "verify_ready.py failed: $(echo "$V" | tail -2 | tr '\n' ' ' | cut -c1-300)"
CMD=$(python3 -c "import json;print(json.load(open('$P/ready.json'))['chain_command'])") || refuse "ready.json unreadable"
got=$(printf '%s' "$CMD" | sha256sum | cut -d' ' -f1); [ "$WANT" = "$got" ] || refuse "chain_command digest differs from READY ($got vs $WANT)"
case "$CMD" in "systemd-run --user --unit=$UNIT --property=Restart=no --property=SendSIGKILL=no --property=TimeoutStopSec=infinity --property=Nice=0 --working-directory=/home/steve/llm-optimizations /usr/bin/taskset -c 0-3,16-19 /usr/bin/env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH=/opt/intel/oneapi/"*" OMP_NUM_THREADS=2 /usr/bin/python3 -B /home/steve/llm-optimizations/$P/queue_runner.py --authorized-device-window --card 0 --view down-tile16 --output-root $OUT --fault-review $FR < /dev/null") ;; *) refuse "unexpected chain command";; esac
case "$CMD" in *'$'*) refuse "chain command contains a shell expansion";; esac
# drain spacing (packet182 p182-chain.sh): never start within 61 s of the previous owner teardown
python3 - <<'PY' 2>/dev/null
import json,time
try: d=json.load(open('experiments/own-xpu-runtime/stage2/screen/v3/teardown-state.json'))
except (OSError,ValueError): d={}
if d.get('drained') and d.get('completed_monotonic'):
    w=max(0.0,min(61.0,d['completed_monotonic']+61.0-time.monotonic()))
    if w>0: print('drain spacing wait',round(w,1)); time.sleep(w)
PY
if [ $DRY = 1 ]; then
  T=/home/steve/llm-optimizations/$P/evidence/.dry-run-fault-review-$(date -u +%Y%m%dT%H%M%SZ).json
  if cpu "$P/fault_review.py" --output "$T" >> "$LOG" 2>&1; then rm -f "$T" "${T%.json}.kernel.jsonl.gz"; log "dry run: fault review captures cleanly (exactly two known fault lines on this boot); temporary capture removed"
  else rm -f "$T" "${T%.json}.kernel.jsonl.gz"; refuse "fault review refused on this boot (see $LOG)"; fi
  log "dry run: every check passed; would run: $CMD"; exit 0
fi
cpu "$P/fault_review.py" --output "$FR" >> "$LOG" 2>&1 || refuse "fault review refused; no launch"
log "all checks passed; fault review $FR; launching: $CMD"
bash -c "$CMD" >> "$LOG" 2>&1 || refuse "systemd-run returned non-zero (no retry)"
dl=$(( $(date +%s) + 120 ))
until s=$(timeout 30 systemctl --user is-active "$UNIT" 2>/dev/null); [ "$s" = active ] || [ "$s" = failed ] || [ "$s" = inactive ]; do
  [ $(date +%s) -gt $dl ] && { log "deadline: $UNIT not active within 120 s (state $s); inspect the unit, no retry"; exit 3; }; sleep 5; done
log "$UNIT is $s; the chain owns card 0 and the host now (no retry, no PAUSE/endpoint change by this launcher)"
[ "$s" = active ] || exit 2
exit 0
