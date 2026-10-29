#!/usr/bin/env bash
# Rank-0 TP device phase (2026-10-29; SC117 rank 0 with the MTP draft, cards 0000:23:00.0 + 0000:47:00.0).
# Launched once, holding both card locks:
#   systemd-run --user --unit=tp-rank0-<phase> --collect -p LimitNOFILE=1048576 -E TP_RUNS=... \
#     flock -n -E 75 /dev/shm/card23.lock flock -n -E 75 /dev/shm/card47.lock taskset -c 0-3,16-19 \
#     bash run_rank0_arms.sh <phase> ARM...
# ARM = name:steps:mode:pattern; mode one | tp (Stage 2b: GDN heads, rows, compact slots, direct
# exchange, two submission threads); pattern = tp_rank0_driver.py --pattern (n/h/m/c). Every arm: marker check,
# driver run, kernel-log check. Any xe/fault line, nonzero exit or exchange timeout halts; nothing is retried.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/direct-exchange-2026-10-28
RUNS=${TP_RUNS:-/dev/shm/tp-rank0-20261029/runs}
CACHE=$(dirname "$RUNS")/cache
PHASE=$1; shift
exec >>"$D/logs/$PHASE.log" 2>&1
echo "=== phase $PHASE start $(date -Is) pid $$ affinity $(taskset -pc $$ | sed 's/.*: //') nofile $(ulimit -n)"
echo "started $PHASE" >"$D/logs/STATUS"
halt() { echo "HALT: $1"; echo "HALT $PHASE: $1" >"$D/logs/STATUS"; exit 1; }
T0=$(date +%s)
python3 "$D/klog_check.py" "$PHASE-before-24h" $(( T0 - 86400 )) "$D/logs/kernel-log-$PHASE-before-24h.txt" || halt "kernel log not clean before phase"
mkdir -p "$RUNS"
for arm in "$@"; do
  IFS=: read -r name steps mode pattern cancel <<<"$arm"
  cancel=${cancel:--1}
  [ -e /dev/shm/sc117-cut16-test.active ] && halt "coordination marker present before $name"
  out="$RUNS/$name"
  [ -e "$out" ] && halt "$out exists (fresh outputs only)"
  case "$mode" in
    one) tp=(); envs=() ;;
    tp) tp=(--tp --split .attention,.gdn.qkv); envs=(OWNRT_TP_EXPERTS=compact OWNRT_TP_EXCHANGE=direct OWNRT_TP_THREADS=1 OWNRT_TP_GDN=heads) ;;
    *) halt "unknown mode $mode" ;;
  esac
  t=$(date +%s)
  echo "--- arm $name steps=$steps mode=$mode pattern=$pattern cancel=$cancel env=${envs[*]:-none} at $(date -Is)"
  env "${envs[@]}" python3 -B "$D/tp_rank0_driver.py" run --launch "$D/rank0-launch-c4096.json" --out "$out" \
    --steps "$steps" --prompt 0 --pattern "$pattern" --cancel-launch "$cancel" --cache "$CACHE" "${tp[@]}"
  rc=$?; echo "arm $name rc=$rc after $(( $(date +%s) - t )) s"
  python3 "$D/klog_check.py" "$PHASE-after-$name" "$t" "$D/logs/kernel-log-$PHASE-after-$name.txt" || halt "kernel log after $name"
  [ "$rc" -eq 0 ] || { tail -30 "$out/rank0.log"; cat "$out"/rank0/failure.txt 2>/dev/null; halt "arm $name rc=$rc"; }
  x=$(ls "$out"/rank0/tp-exchange.json 2>/dev/null | head -1)
  if [ -n "$x" ]; then
    cat "$x"; echo
    python3 -c "import json,sys;d=json.load(open('$x'));sys.exit(1 if any(c['timeouts'] or c['abort'] for c in d['cards']) else 0)" \
      || halt "exchange timeout/abort in $name"
  fi
  python3 -c "import json;d=json.load(open('$out/summary.json'));print('events',d.get('events'),'tokens',d['draft_tokens'][:6])"
done
echo "=== phase $PHASE done $(date -Is)"
echo "done $PHASE" >"$D/logs/STATUS"
