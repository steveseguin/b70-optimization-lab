#!/usr/bin/env bash
# Device phase of research/tp/service-ready-2026-10-29 (rank drivers alone, cards 0000:23:00.0 + 0000:47:00.0).
# Launched once as a transient unit that already holds both card locks:
#   systemd-run --user --unit=svc-ready-<phase> --collect -p LimitNOFILE=1048576 -E SR_RUNS=... \
#     flock -n -E 75 /dev/shm/card23.lock flock -n -E 75 /dev/shm/card47.lock taskset -c 0-3,16-19 bash run_phase.sh <phase> ARM...
# ARM = name:rank:mode:steps:prompt:pattern:extra  rank 0|1; mode one | tp (Stage 2b layout: GDN heads, rows, compact
# slots, direct exchange, two submission threads); prompt = rows read before decode (rank 1: token by token unless extra
# has "batched"); pattern = rank-0 --pattern; extra = comma list (batched, rows=N, prefill-alloc; rank 0: tbt = prompt token
# by token, otherwise PREFILL chunks).
# Per arm: MemAvailable and /dev/shm floors, fresh output, driver run, kernel-log check, exchange-statistics check.
# Any xe/fault line, nonzero exit, exchange timeout or card mismatch halts; nothing is retried. Do not edit while it runs.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/service-ready-2026-10-29
KL=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/e2e-suite-2026-10-29/klog_check.py
RUNS=${SR_RUNS:-/dev/shm/svc-ready-20261029/runs}
BIN=${SR_BIN:-fc18c9b0fe6a}   # launch JSONs rank<r>-launch-c65536-<BIN>.json (make_launch.py)
CACHE=$(dirname "$RUNS")/cache
PHASE=$1; shift
exec >>"$D/logs/$PHASE.log" 2>&1
echo "=== phase $PHASE binary $BIN start $(date -Is) pid $$ affinity $(taskset -pc $$ | sed 's/.*: //') nofile $(ulimit -n)"
echo "started $PHASE" >"$D/logs/STATUS"
halt() { echo "HALT: $1"; echo "HALT $PHASE: $1" >"$D/logs/STATUS"; exit 1; }
T0=$(date +%s)
python3 "$KL" "$PHASE-before-24h" $(( T0 - 86400 )) "$D/logs/kernel-log-$PHASE-before-24h.txt" || halt "kernel log not clean before phase"
mkdir -p "$RUNS"
for arm in "$@"; do
  IFS=: read -r name rank mode steps prompt pattern extra <<<"$arm"
  out="$RUNS/$name"
  [ -e "$out" ] && halt "$out exists (fresh outputs only)"
  avail=$(awk '/^MemAvailable:/{print $2*1024}' /proc/meminfo); shm=$(df -B1 --output=avail /dev/shm | tail -1)
  echo "--- arm $name rank=$rank mode=$mode steps=$steps prompt=$prompt pattern=$pattern extra=$extra MemAvailable=$avail shm_free=$shm at $(date -Is)"
  [ "$avail" -ge 64000000000 ] || halt "MemAvailable $avail below 64 GB before $name"
  [ "$shm" -ge 12000000000 ] || halt "/dev/shm free $shm below 12 GB before $name"
  case "$mode" in
    one) tp=(); envs=() ;;
    tp) tp=(--tp --split .attention,.gdn.qkv); envs=(OWNRT_TP_EXPERTS=compact OWNRT_TP_EXCHANGE=direct OWNRT_TP_THREADS=1 OWNRT_TP_GDN=heads) ;;
    *) halt "unknown mode $mode" ;;
  esac
  more=()
  for x in ${extra//,/ }; do case "$x" in batched) more+=(--batched) ;; tbt) more+=(--token-prompt) ;; prefill-alloc) more+=(--prefill-alloc) ;; rows=*) more+=(--rows "${x#rows=}") ;; "") ;; *) halt "unknown extra $x" ;; esac; done
  t=$(date +%s)
  if [ "$rank" = 1 ]; then
    env "${envs[@]}" python3 -B "$D/tp_rank1_driver.py" run --launch "$D/rank1-launch-c65536-$BIN.json" --out "$out" \
      --steps "$steps" --prompt "$prompt" --cache "$CACHE" "${tp[@]}" "${more[@]}"
  else
    env "${envs[@]}" python3 -B "$D/tp_rank0_driver.py" run --launch "$D/rank0-launch-c65536-$BIN.json" --out "$out" \
      --steps "$steps" --prompt "$prompt" --pattern "$pattern" --cache "$CACHE" "${tp[@]}" "${more[@]}"
  fi
  rc=$?; echo "arm $name rc=$rc after $(( $(date +%s) - t )) s"
  python3 "$KL" "$PHASE-after-$name" "$t" "$D/logs/kernel-log-$PHASE-after-$name.txt" || halt "kernel log after $name"
  [ "$rc" -eq 0 ] || { tail -30 "$out/rank$rank.log"; cat "$out/rank$rank/failure.txt" 2>/dev/null; halt "arm $name rc=$rc"; }
  x="$out/rank$rank/tp-exchange.json"
  if [ -f "$x" ]; then
    cat "$x"; echo
    python3 -c "import json,sys;d=json.load(open('$x'));sys.exit(1 if any(c['timeouts'] or c['abort'] for c in d['cards']) else 0)" \
      || halt "exchange timeout/abort in $name"
  fi
  c="$out/rank$rank/tp-replicate-compare.json"
  if [ -f "$c" ]; then head -c 400 "$c"; echo
    python3 -c "import json,sys;sys.exit(0 if json.load(open('$c'))['passed'] else 1)" || halt "card 1 differs from card 0 in $name"
  elif [ "$mode" = tp ]; then halt "no tp-replicate-compare.json in $name"; fi
  grep -h "owned\|planned_bytes" "$out/rank$rank.log" | head -6
done
echo "=== phase $PHASE done $(date -Is)"
echo "done $PHASE" >"$D/logs/STATUS"
