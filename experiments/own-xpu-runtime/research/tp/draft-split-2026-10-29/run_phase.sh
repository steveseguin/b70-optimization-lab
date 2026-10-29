#!/usr/bin/env bash
# Device phase of research/tp/draft-split-2026-10-29 (rank drivers alone; from service-ready-2026-10-29/run_phase.sh).
# Launched once as a transient unit that already holds all four card locks:
#   systemd-run --user --unit=draft-split-<phase> --collect -p LimitNOFILE=1048576 -E DS_RUNS=... \
#     flock -n -E 75 /dev/shm/card23.lock flock -n -E 75 /dev/shm/card27.lock flock -n -E 75 /dev/shm/card43.lock \
#     flock -n -E 75 /dev/shm/card47.lock taskset -c 0-3,16-19 bash run_phase.sh <phase> ARM...
# ARM = name:rank:mode:steps:prompt:pattern:extra  rank 0|1; mode one | tp (Stage 2b layout: GDN heads, rows, compact
# slots, direct exchange, two submission threads) | tps (tp + OWNRT_DRAFT_HEAD_SPLIT=1, rank 0); prompt = rows read
# before decode; pattern = rank-0 --pattern; extra = comma list (batched, tbt, prefill-alloc, rows=N, pair=a.b (the
# --tp card pair, PCI-order indices: 0=23 1=27 2=43 3=47; default 0.1 = rank 0's service cards), rows0=N
# (OWNRT_DRAFT_HEAD_SPLIT_ROWS), launch=TAG (rank<r>-launch-c65536-TAG.json instead of the binary's)).
# Per arm: MemAvailable and /dev/shm floors, fresh output, driver run, kernel-log check, exchange-statistics checks
# (target exchanges and the draft head split's own). Any xe/fault line, nonzero exit, exchange timeout or card
# mismatch halts; nothing is retried. Do not edit while it runs.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/draft-split-2026-10-29
SR=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/service-ready-2026-10-29
KL=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/e2e-suite-2026-10-29/klog_check.py
RUNS=${DS_RUNS:-/dev/shm/draft-split-20261029/runs}
BIN=${DS_BIN:-46891d491b08}
CACHE=$(dirname "$RUNS")/cache
PHASE=$1; shift
exec >>"$D/logs/$PHASE.log" 2>&1
echo "=== phase $PHASE binary $BIN start $(date -Is) pid $$ affinity $(taskset -pc $$ | sed 's/.*: //') nofile $(ulimit -n)"
echo "started $PHASE" >"$D/logs/STATUS"
halt() { echo "HALT: $1"; echo "HALT $PHASE: $1" >"$D/logs/STATUS"; exit 1; }
for f in /dev/shm/card23.lock /dev/shm/card27.lock /dev/shm/card43.lock /dev/shm/card47.lock; do flock -n "$f" true && halt "$f is not held"; done
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
  envs=(); tp=()
  case "$mode" in
    one) ;;
    tp|tps) tp=(--tp --split .attention,.gdn.qkv); envs=(OWNRT_TP_EXPERTS=compact OWNRT_TP_EXCHANGE=direct OWNRT_TP_THREADS=1 OWNRT_TP_GDN=heads)
            [ "$mode" = tps ] && envs+=(OWNRT_DRAFT_HEAD_SPLIT=1) ;;
    *) halt "unknown mode $mode" ;;
  esac
  more=(); pair=0,1; launch=$BIN
  for x in ${extra//,/ }; do case "$x" in batched) more+=(--batched) ;; tbt) more+=(--token-prompt) ;; prefill-alloc) more+=(--prefill-alloc) ;;
    rows=*) more+=(--rows "${x#rows=}") ;; pair=*) pair=${x#pair=}; pair=${pair/./,} ;; rows0=*) envs+=(OWNRT_DRAFT_HEAD_SPLIT_ROWS=${x#rows0=}) ;;
    launch=*) launch=${x#launch=} ;; "") ;; *) halt "unknown extra $x" ;; esac; done
  [ "$mode" = one ] || more+=(--pair "$pair")
  L="$D/rank$rank-launch-c65536-$launch.json"; [ -f "$L" ] || halt "no launch $L"
  t=$(date +%s)
  if [ "$rank" = 1 ]; then
    env "${envs[@]}" python3 -B "$SR/tp_rank1_driver.py" run --launch "$L" --out "$out" \
      --steps "$steps" --prompt "$prompt" --cache "$CACHE" "${tp[@]}" "${more[@]}"
  else
    env "${envs[@]}" python3 -B "$SR/tp_rank0_driver.py" run --launch "$L" --out "$out" \
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
  s="$out/rank$rank/draft-final-state/draft-head-split-exchange.json"
  if [ -f "$s" ]; then
    cat "$s"; echo
    python3 -c "import json,sys;d=json.load(open('$s'));sys.exit(1 if d['card1_error'] or any(c['timeouts'] or c['abort'] for c in d['cards']) else 0)" \
      || halt "draft head split exchange timeout/abort/error in $name"
  elif [ "$mode" = tps ]; then halt "no draft-head-split-exchange.json in $name"; fi
  c="$out/rank$rank/tp-replicate-compare.json"
  if [ -f "$c" ]; then head -c 400 "$c"; echo
    python3 -c "import json,sys;sys.exit(0 if json.load(open('$c'))['passed'] else 1)" || halt "card 1 differs from card 0 in $name"
  elif [ "$mode" != one ]; then halt "no tp-replicate-compare.json in $name"; fi
  grep -h "owned\|planned_bytes" "$out/rank$rank.log" | head -6
done
echo "=== phase $PHASE done $(date -Is)"
echo "done $PHASE" >"$D/logs/STATUS"
