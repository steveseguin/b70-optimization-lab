#!/usr/bin/env bash
# Device phase for the 2026-10-28 direct-exchange TP lab (rank 1 of SC117, cards 0000:23:00.0 + 0000:47:00.0).
# Launched once, already holding both card locks:
#   systemd-run --user --unit=tp-direct-<phase> --collect flock -n -E 75 /dev/shm/card23.lock \
#     flock -n -E 75 /dev/shm/card47.lock taskset -c 0-3,16-19 bash run_arms.sh <phase> ARM...
# ARM = name:steps:mode, mode one | one47 | rep | rep-threads | copy | direct | direct-threads | dense-direct | slot-direct |
#   xonly-threads (exact diagnostic: no split, the same exchanges of identical rows) | heads-threads (Stage 2) |
#   heads-alone-threads (Stage 2 head split with nothing else split) | compact-threads (Stage 2b: Stage 2 with compact
#   expert slots instead of masked ones).
# Order per arm: coordination-marker check -> engine run (tp_rank1_driver.py) -> kernel-log check. Any xe/fault line,
# nonzero exit or exchange timeout halts the phase; nothing is retried. Do not edit while it runs.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/direct-exchange-2026-10-28
ENGINE=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine
RUNS=${TP_RUNS:-/dev/shm/tp-direct-20261028/runs}   # Stage 2: TP_RUNS=/dev/shm/tp-heads-20261028/runs
CACHE=$(dirname "$RUNS")/cache
PHASE=$1; shift
exec >>"$D/logs/$PHASE.log" 2>&1
echo "=== phase $PHASE start $(date -Is) pid $$ affinity $(taskset -pc $$ | sed 's/.*: //')"
echo "started $PHASE" >"$D/logs/STATUS"
halt() { echo "HALT: $1"; echo "HALT $PHASE: $1" >"$D/logs/STATUS"; exit 1; }
T0=$(date +%s)
python3 "$D/klog_check.py" "$PHASE-before-24h" $(( T0 - 86400 )) "$D/logs/kernel-log-$PHASE-before-24h.txt" || halt "kernel log not clean before phase"
mkdir -p "$RUNS"
for arm in "$@"; do
  IFS=: read -r name steps mode <<<"$arm"
  [ -e /dev/shm/sc117-cut16-test.active ] && halt "coordination marker present before $name"
  out="$RUNS/$name"
  [ -e "$out" ] && halt "$out exists (fresh outputs only)"
  tp=(--tp --split .attention,.gdn.qkv); envs=(OWNRT_TP_EXPERTS=slot)
  case "$mode" in
    one) tp=(); envs=() ;;
    one47) tp=(); envs=() ;;  # one card on 0000:47:00.0 instead of 23:00.0
    rep) tp=(--tp); envs=() ;;
    copy) envs+=(OWNRT_TP_EXCHANGE=copy) ;;
    direct) envs+=(OWNRT_TP_EXCHANGE=direct) ;;
    direct-threads) envs+=(OWNRT_TP_EXCHANGE=direct OWNRT_TP_THREADS=1) ;;
    dense-direct) envs=(OWNRT_TP_EXCHANGE=direct) ;;
    slot-direct) tp=(--tp); envs+=(OWNRT_TP_EXCHANGE=direct) ;;
    rep-threads) tp=(--tp); envs=(OWNRT_TP_THREADS=1) ;;
    heads-threads) envs+=(OWNRT_TP_EXCHANGE=direct OWNRT_TP_THREADS=1 OWNRT_TP_GDN=heads) ;;  # Stage 2: + GDN head split
    compact-threads) envs=(OWNRT_TP_EXPERTS=compact OWNRT_TP_EXCHANGE=direct OWNRT_TP_THREADS=1 OWNRT_TP_GDN=heads) ;;  # Stage 2b
    heads-alone-threads) tp=(--tp); envs=(OWNRT_TP_EXCHANGE=direct OWNRT_TP_THREADS=1 OWNRT_TP_GDN=heads) ;;  # head split only
    xonly-threads) envs+=(OWNRT_TP_EXCHANGE=direct-replicated OWNRT_TP_THREADS=1) ;;  # exact; exchanges with no split
    *) halt "unknown mode $mode" ;;
  esac
  t=$(date +%s)
  echo "--- arm $name steps=$steps mode=$mode env=${envs[*]:-none} tp=${tp[*]:-none} at $(date -Is)"
  launch="$D/rank1-launch-c4096.json"; [ "$mode" = one47 ] && launch="$D/rank1-launch-c4096-card47.json"
  env "${envs[@]}" python3 -B "$ENGINE/tools/tp_rank1_driver.py" run --launch "$launch" --out "$out" \
    --steps "$steps" --cache "$CACHE" "${tp[@]}"
  rc=$?; echo "arm $name rc=$rc after $(( $(date +%s) - t )) s"
  python3 "$D/klog_check.py" "$PHASE-after-$name" "$t" "$D/logs/kernel-log-$PHASE-after-$name.txt" || halt "kernel log after $name"
  [ "$rc" -eq 0 ] || { tail -30 "$out/rank1.log"; halt "arm $name rc=$rc"; }
  if [ -f "$out/rank1/tp-exchange.json" ]; then
    cat "$out/rank1/tp-exchange.json"; echo
    python3 -c "import json,sys;d=json.load(open('$out/rank1/tp-exchange.json'));sys.exit(1 if any(c['timeouts'] or c['abort'] for c in d['cards']) else 0)" \
      || halt "exchange timeout/abort in $name"
  fi
  [ -f "$out/rank1/tp-replicate-compare.json" ] && { cat "$out/rank1/tp-replicate-compare.json" | head -c 600; echo; }
done
echo "=== phase $PHASE done $(date -Is)"
echo "done $PHASE" >"$D/logs/STATUS"
