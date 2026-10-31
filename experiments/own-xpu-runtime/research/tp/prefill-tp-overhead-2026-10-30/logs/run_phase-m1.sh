#!/usr/bin/env bash
# Device phase of research/tp/prefill-tp-overhead-2026-10-30 (copy of prefill-draft-batch-2026-10-30/run_phase.sh; adds st1 =
# OWNRT_SITE_TRACE=1 (one card, with a launch=timing JSON: --timing class) and xs=N = OWNRT_TP_EXCHANGE_STATS=N).
# (prefill-draft-batch-2026-10-30: copy of prefill-host-2026-10-30/run_phase.sh; adds extra db =
# OWNRT_DRAFT_CHUNK_BATCH=1 (both ranks: the service passes it to both; only rank 0 has a draft), and hc = OWNRT_HC_KERNELS=1 of research/hc-kernels-2026-10-30). (prefill-host-2026-10-30: copy of prefill-speed-2026-10-29/run_phase.sh.) Adds extras ep
# (OWNRT_TP_EXPERT_PAIR=1), rd (OWNRT_RETIRE_DEFERRED=1) of fixed-cost-2026-10-30, and the new sr (OWNRT_PREFILL_SPECIAL_ROWS=1),
# lt=N (OWNRT_PREFILL_LOOKUP_THREADS=N), st (OWNRT_DRAFT_CHUNK_STAGE_THREAD=1), gr (OWNRT_DRAFT_CHUNK_GUARD_ROW=1),
# rc (OWNRT_DRAFT_CHUNK_ROW_COPY=1).
# (prefill-speed-2026-10-29: rank drivers alone; copy of ctx131072-2026-10-29/run_phase.sh.)
# Adds extras ht (OWNRT_PREFILL_HOST_TRACE=1, diagnostic host timing), lb (OWNRT_PREFILL_LOOKUP_BATCH=1), mn
# (OWNRT_PREFILL_MOE_NATIVE=1), xz (OWNRT_PREFILL_XZERO_ONCE=1), ko (OWNRT_DRAFT_CHUNK_KV_ONLY=1, with dc), sp=N (the drivers'
# --second-prompt N: RESET, then a second request) and dc
# (OWNRT_DRAFT_CHUNK_REPLAY=1 and the rank-0 driver's --draft-chunk). Everything else is the ctx131072 phase unchanged.
# (ctx131072-2026-10-29:)
# Adds extra ctx=N: the launch JSON rank<r>-launch-c<N>-<tag>.json (default 65536), so one phase can hold 65536 and 131072 arms.
# (fault-ladder-2026-10-29, copy of persistent-thread-2026-10-29/run_phase.sh:)
# Adds: extra trace (the host-only allocation tracer tracer/alloc_trace.so, LD_PRELOAD into the rank-1 engine process
# only, through this folder's tp_rank1_driver.py), extra cc (OWNRT_TP_CARD_CONTEXT=1, the fix under test), a root-disk floor.
# The rank-1 driver is this folder's copy (it also records every call's CLOCK_MONOTONIC times).
# (persistent-thread: extra pt = OWNRT_TP_PERSISTENT_THREAD=1.)
# Adds extra pt (OWNRT_TP_PERSISTENT_THREAD=1). Every TP run must write tp-submit-thread.json: with pt one persistent
# thread for the whole process (threads_created 1, every job completed, not poisoned, joined); without pt one
# per-half thread per job.
# (qsa-split: extra qs = OWNRT_TP_QSA_SPLIT=1; the run must then write qsa-split.json with every QSA layer split).
# Launched once as a transient unit that already holds all four card locks:
#   systemd-run --user --unit=tp-persistent-<phase> --collect -p LimitNOFILE=1048576 -E DS_RUNS=... \
#     flock -n -E 75 /dev/shm/card23.lock flock -n -E 75 /dev/shm/card27.lock flock -n -E 75 /dev/shm/card43.lock \
#     flock -n -E 75 /dev/shm/card47.lock taskset -c 0-3,16-19 bash run_phase.sh <phase> ARM...
# ARM = name:rank:mode:steps:prompt:pattern:extra  rank 0|1; mode one | tp (Stage 2b layout: GDN heads, rows, compact
# slots, direct exchange, two submission threads) | tps (tp + OWNRT_DRAFT_HEAD_SPLIT=1, rank 0) | tpt (tp +
# OWNRT_TARGET_HEAD_SPLIT=1); prompt = rows read
# before decode; pattern = rank-0 --pattern; extra = comma list (batched, tbt, prefill-alloc, rows=N, pair=a.b (the
# --tp card pair, PCI-order indices: 0=23 1=27 2=43 3=47; default 0.1), rows0=N (OWNRT_DRAFT_HEAD_SPLIT_ROWS),
# trows0=N (OWNRT_TARGET_HEAD_SPLIT_ROWS), launch=TAG (rank<r>-launch-c65536-TAG.json instead of the binary's),
# nw (OWNRT_SNAPSHOT_NOWAIT=1), gs (OWNRT_DRAFT_GEMV_SPLIT=1), gsites=a+b (OWNRT_DRAFT_GEMV_SPLIT_SITES=a,b),
# rb (OWNRT_ROLLBACK_NOWAIT=1)). The rank-0 driver is this
# folder's lab copy (same commands; it also times speculative halves, rollbacks and redos).
# Per arm: MemAvailable and /dev/shm floors, fresh output, driver run, kernel-log check, exchange-statistics checks
# (target exchanges and the draft head split's own). Any xe/fault line, nonzero exit, exchange timeout or card
# mismatch halts; nothing is retried. Do not edit while it runs.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-tp-overhead-2026-10-30
SR=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/service-ready-2026-10-29
KL=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/e2e-suite-2026-10-29/klog_check.py
RUNS=${DS_RUNS:-/dev/shm/prefill-tp-overhead-20261030/runs}
TRACE_SO=${DS_TRACE_SO:-/dev/shm/prefill-tp-overhead-20261030/alloc_trace.so}
BIN=${DS_BIN:-unset}
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
  root=$(df -B1 --output=avail / | tail -1); [ "$root" -ge 27200000000 ] || halt "root free $root below 27.2 GB before $name"
  envs=(); tp=()
  case "$mode" in
    one) ;;
    tp|tps|tpt) tp=(--tp --split .attention,.gdn.qkv); envs=(OWNRT_TP_EXPERTS=compact OWNRT_TP_EXCHANGE=direct OWNRT_TP_THREADS=1 OWNRT_TP_GDN=heads)
            [ "$mode" = tps ] && envs+=(OWNRT_DRAFT_HEAD_SPLIT=1); [ "$mode" = tpt ] && envs+=(OWNRT_TARGET_HEAD_SPLIT=1) ;;
    *) halt "unknown mode $mode" ;;
  esac
  more=(); pair=0,1; launch=$BIN; ctx=65536
  for x in ${extra//,/ }; do case "$x" in batched) more+=(--batched) ;; tbt) more+=(--token-prompt) ;; prefill-alloc) more+=(--prefill-alloc) ;;
    rows=*) more+=(--rows "${x#rows=}") ;; pair=*) pair=${x#pair=}; pair=${pair/./,} ;; rows0=*) envs+=(OWNRT_DRAFT_HEAD_SPLIT_ROWS=${x#rows0=}) ;; trows0=*) envs+=(OWNRT_TARGET_HEAD_SPLIT_ROWS=${x#trows0=}) ;;
    launch=*) launch=${x#launch=} ;; ctx=*) ctx=${x#ctx=} ;; nw) envs+=(OWNRT_SNAPSHOT_NOWAIT=1) ;; gs) envs+=(OWNRT_DRAFT_GEMV_SPLIT=1) ;; rb) envs+=(OWNRT_ROLLBACK_NOWAIT=1) ;;
    gsites=*) v=${x#gsites=}; envs+=(OWNRT_DRAFT_GEMV_SPLIT_SITES=${v//+/,}) ;; qs) envs+=(OWNRT_TP_QSA_SPLIT=1) ;; pt) envs+=(OWNRT_TP_PERSISTENT_THREAD=1) ;;
    trace) [ "$rank" = 1 ] || halt "trace is rank 1 only"; [ -f "$TRACE_SO" ] || halt "no $TRACE_SO"; envs+=(ALLOC_TRACE_SO=$TRACE_SO) ;; cc) envs+=(OWNRT_TP_CARD_CONTEXT=1) ;;
    ht) envs+=(OWNRT_PREFILL_HOST_TRACE=1) ;; lb) envs+=(OWNRT_PREFILL_LOOKUP_BATCH=1) ;;
    mn) envs+=(OWNRT_PREFILL_MOE_NATIVE=1) ;; xz) envs+=(OWNRT_PREFILL_XZERO_ONCE=1) ;;
    dc) [ "$rank" = 0 ] || halt "dc is rank 0 only"; envs+=(OWNRT_DRAFT_CHUNK_REPLAY=1); more+=(--draft-chunk) ;;
    ko) [ "$rank" = 0 ] || halt "ko is rank 0 only"; envs+=(OWNRT_DRAFT_CHUNK_KV_ONLY=1) ;;
    sp=*) more+=(--second-prompt "${x#sp=}") ;;
    ep) envs+=(OWNRT_TP_EXPERT_PAIR=1) ;; rd) envs+=(OWNRT_RETIRE_DEFERRED=1) ;;
    sr) envs+=(OWNRT_PREFILL_SPECIAL_ROWS=1) ;; lt=*) envs+=(OWNRT_PREFILL_LOOKUP_THREADS=${x#lt=}) ;;
    st) [ "$rank" = 0 ] || halt "st is rank 0 only"; envs+=(OWNRT_DRAFT_CHUNK_STAGE_THREAD=1) ;; gr) [ "$rank" = 0 ] || halt "gr is rank 0 only"; envs+=(OWNRT_DRAFT_CHUNK_GUARD_ROW=1) ;;
    rc) [ "$rank" = 0 ] || halt "rc is rank 0 only"; envs+=(OWNRT_DRAFT_CHUNK_ROW_COPY=1) ;;
    db) envs+=(OWNRT_DRAFT_CHUNK_BATCH=1) ;; hc) envs+=(OWNRT_HC_KERNELS=1) ;;
    st1) [ "$mode" = one ] || halt "st1 (site trace / class timing) on one card only"; envs+=(OWNRT_SITE_TRACE=1) ;;  # prefill-tp-overhead: with launch=timing
    xs=*) [ "$mode" != one ] || halt "xs needs TP"; envs+=(OWNRT_TP_EXCHANGE_STATS=${x#xs=}) ;;  # prefill-tp-overhead: per-site exchange statistics  # db on rank 1: the service passes it to both ranks (no draft there)
    "") ;; *) halt "unknown extra $x" ;; esac; done
  [ "$mode" = one ] || more+=(--pair "$pair")
  L="$D/rank$rank-launch-c$ctx-$launch.json"; [ -f "$L" ] || halt "no launch $L"
  grep -q -- "\"--context\", \"$ctx\"" "$L" || python3 -c "import json,sys;a=json.load(open('$L'))['argv'];sys.exit(0 if a[a.index('--context')+1]=='$ctx' else 1)" || halt "launch $L is not context $ctx"
  t=$(date +%s)
  if [ "$rank" = 1 ]; then
    env "${envs[@]}" python3 -B "$D/tp_rank1_driver.py" run --launch "$L" --out "$out" \
      --steps "$steps" --prompt "$prompt" --cache "$CACHE" "${tp[@]}" "${more[@]}"
  else
    env "${envs[@]}" python3 -B "$D/tp_rank0_driver.py" run --launch "$L" --out "$out" \
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
  g="$out/rank$rank/draft-final-state/draft-gemv-split-exchange.json"
  if [ -f "$g" ]; then
    cat "$g"; echo; cat "$out/rank$rank/draft-gemv-split.json"; echo
    python3 -c "import json,sys;d=json.load(open('$g'));sys.exit(1 if d['card1_error'] or not d['runs'] or any(c['timeouts'] or c['abort'] for c in d['cards']) else 0)" \
      || halt "draft GEMV split exchange timeout/abort/error in $name"
  elif [[ ",$extra," == *",gs,"* ]]; then halt "no draft-gemv-split-exchange.json in $name"; fi
  h="$out/rank$rank/target-head-split.json"
  if [ "$mode" = tpt ]; then [ -f "$h" ] || halt "no target-head-split.json in $name"; cat "$h"; echo
    [ "$rank" = 1 ] && { python3 -c "import json,sys;sys.exit(0 if json.load(open('$h'))['applied'] else 1)" || halt "target head split not applied in $name"; }
  fi
  q="$out/rank$rank/qsa-split.json"
  if [[ ",$extra," == *",qs,"* ]]; then [ -f "$q" ] || halt "no qsa-split.json in $name"; cat "$q"; echo
    want=$([ "$rank" = 1 ] && echo 7 || echo 5)
    python3 -c "import json,sys;d=json.load(open('$q'));sys.exit(0 if d['layers']==$want and d['kv_buffers_halved']==2*$want else 1)" || halt "QSA split not applied to all $want layers in $name"
  elif [ -f "$q" ]; then halt "qsa-split.json without qs in $name"; fi
  p="$out/rank$rank/tp-submit-thread.json"
  if [ "$mode" != one ]; then [ -f "$p" ] || halt "no tp-submit-thread.json in $name"; cat "$p"; echo
    want=$([[ ",$extra," == *",pt,"* ]] && echo True || echo False)
    python3 -c "import json,sys;d=json.load(open('$p'));ok=d['persistent']==$want and not d['error'] and (d['threads_created']==1 and d['jobs']==d['published']==d['completed'] and not d['poisoned'] and d['joined'] if $want else d['threads_created']==d['jobs']>0);sys.exit(0 if ok else 1)" \
      || halt "card-1 submission thread record wrong in $name"
  elif [ -f "$p" ]; then halt "tp-submit-thread.json in a one-card run $name"; fi
  c="$out/rank$rank/tp-replicate-compare.json"
  if [ -f "$c" ]; then head -c 400 "$c"; echo
    python3 -c "import json,sys;sys.exit(0 if json.load(open('$c'))['passed'] else 1)" || halt "card 1 differs from card 0 in $name"
  elif [ "$mode" != one ]; then halt "no tp-replicate-compare.json in $name"; fi
  grep -h "owned\|planned_bytes" "$out/rank$rank.log" | head -6
done
echo "=== phase $PHASE done $(date -Is)"
echo "done $PHASE" >"$D/logs/STATUS"
