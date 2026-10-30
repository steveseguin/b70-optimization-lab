#!/usr/bin/env bash
# Device phase of research/tp/fixed-cost-2026-10-30 (copy of research/tp/stage-overhead-2026-10-30/run_phase.sh) (rank drivers of research/tp/prefill-speed-2026-10-29, unchanged;
# safety checks copied from that folder's run_phase.sh). Launched once as a transient unit that already holds the locks:
#   systemd-run --user --unit=stage-overhead-<phase> --collect -p Restart=no -p KillMode=process -p LimitNOFILE=1048576 \
#     -E SO_BIN=... flock -n -E 75 /dev/shm/card23.lock flock -n -E 75 /dev/shm/card27.lock flock -n -E 75 /dev/shm/card47.lock \
#     taskset -c 0-3,16-19 bash run_phase.sh <phase> ARM...
# ARM = name:rank:mode:steps:prompt:pattern:extra
#   mode one   one card (0000:23:00.0)
#        full  the record's four-card decode set (tptsxqc): rank 1 on 23+47, rank 0 on 23+27
#        rep   --tp-replicate with nothing split and no exchange (two-card process cost), card contexts, two threads
#        xonly OWNRT_TP_EXCHANGE=direct-replicated + OWNRT_TP_SPLIT=.attention,.gdn.qkv: nothing split, the row-split
#              sites' exchanges run anyway (exact diagnostic: exchange cost alone)
#        probe0|probe1  ONE card, OWNRT_TP_SHAPE_PROBE=c: card c's launches of the full TP plan, no exchanges (timing only,
#              outputs NOT exact)
#   prompt rows are read token by token (decode halves); pattern = rank-0 --pattern
#   extra (fixed-cost): ep (OWNRT_TP_EXPERT_PAIR=1), batched (prompt through PREFILL chunks of 256 rows), sp=N (the
#          drivers' --second-prompt N: RESET, then a second request), F-flags as added
#   extra: xs=N (OWNRT_TP_EXCHANGE_STATS=N), pt (OWNRT_TP_PERSISTENT_THREAD=1), nw (rank 0: OWNRT_SNAPSHOT_NOWAIT=1 OWNRT_ROLLBACK_NOWAIT=1), trace (OWNRT_SITE_TRACE=1 + --timing launch; one-card modes only)
# Per arm: MemAvailable / shm / root floors, fresh output, driver run, kernel-log check, exchange-statistics checks.
# Any xe/fault line, nonzero exit, exchange timeout or card mismatch halts; nothing is retried. Do not edit while it runs.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/fixed-cost-2026-10-30
PS=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-speed-2026-10-29
RUNS=${SO_RUNS:-/dev/shm/fixed-cost-20261030/runs}
BIN=${SO_BIN:-unset}
CACHE=$(dirname "$RUNS")/cache
PHASE=$1; shift
exec >>"$D/logs/$PHASE.log" 2>&1
echo "=== phase $PHASE binary $BIN ($(sha256sum "$BIN" | cut -c1-12)) start $(date -Is) pid $$ affinity $(taskset -pc $$ | sed 's/.*: //') nofile $(ulimit -n)"
echo "started $PHASE" >"$D/logs/STATUS"
halt() { echo "HALT: $1"; echo "HALT $PHASE: $1" >"$D/logs/STATUS"; exit 1; }
T0=$(date +%s)
python3 "$D/klog.py" "$PHASE-before-24h" $(( T0 - 86400 )) "$D/logs/kernel-log-$PHASE-before-24h.txt" || halt "kernel log not clean before phase"
mkdir -p "$RUNS" "$D/launch"
for arm in "$@"; do
  IFS=: read -r name rank mode steps prompt pattern extra <<<"$arm"
  out="$RUNS/$name"
  [ -e "$out" ] && halt "$out exists (fresh outputs only)"
  avail=$(awk '/^MemAvailable:/{print $2*1024}' /proc/meminfo); shm=$(df -B1 --output=avail /dev/shm | tail -1)
  echo "--- arm $name rank=$rank mode=$mode steps=$steps prompt=$prompt pattern=$pattern extra=$extra MemAvailable=$avail shm_free=$shm at $(date -Is)"
  [ "$avail" -ge 64000000000 ] || halt "MemAvailable $avail below 64 GB before $name"
  [ "$shm" -ge 12000000000 ] || halt "/dev/shm free $shm below 12 GB before $name"
  root=$(df -B1 --output=avail / | tail -1); [ "$root" -ge 27000000000 ] || halt "root free $root below 27 GB before $name"
  pair=$([ "$rank" = 1 ] && echo 0,3 || echo 0,1)
  envs=(NEOReadDebugKeys=1 EnableDeferBacking=0); tp=(); more=(--token-prompt)
  [ "$rank" = 1 ] && more=()   # the rank-1 driver reads the prompt token by token unless --batched
  full=(OWNRT_TP_EXPERTS=compact OWNRT_TP_EXCHANGE=direct OWNRT_TP_GDN=heads OWNRT_TP_QSA_SPLIT=1)
  [ "$rank" = 1 ] && full+=(OWNRT_TARGET_HEAD_SPLIT=1)
  r0=(OWNRT_DRAFT_HEAD_SPLIT=1 OWNRT_SNAPSHOT_NOWAIT=1 OWNRT_DRAFT_GEMV_SPLIT=1 OWNRT_ROLLBACK_NOWAIT=1)
  case "$mode" in
    one) ;;
    full) tp=(--tp --split .attention,.gdn.qkv --pair "$pair"); envs+=("${full[@]}" OWNRT_TP_THREADS=1 OWNRT_TP_CARD_CONTEXT=1)
          [ "$rank" = 0 ] && envs+=("${r0[@]}") ;;
    rep) tp=(--tp --pair "$pair"); envs+=(OWNRT_TP_THREADS=1 OWNRT_TP_CARD_CONTEXT=1 OWNRT_TP_EXCHANGE=direct)
          [ "$rank" = 0 ] && envs+=(OWNRT_SNAPSHOT_NOWAIT=1 OWNRT_ROLLBACK_NOWAIT=1) ;;
    xonly) tp=(--tp --split .attention,.gdn.qkv --pair "$pair"); envs+=(OWNRT_TP_EXCHANGE=direct-replicated OWNRT_TP_THREADS=1 OWNRT_TP_CARD_CONTEXT=1)
          [ "$rank" = 0 ] && envs+=(OWNRT_SNAPSHOT_NOWAIT=1 OWNRT_ROLLBACK_NOWAIT=1) ;;
    probe0|probe1) envs+=("${full[@]}" OWNRT_TP_SPLIT=.attention,.gdn.qkv OWNRT_TP_SHAPE_PROBE=${mode#probe}) ;;
    *) halt "unknown mode $mode" ;;
  esac
  launch=default; lenv=()
  for x in ${extra//,/ }; do case "$x" in
    xs=*) envs+=(OWNRT_TP_EXCHANGE_STATS=${x#xs=}) ;;
    pt) envs+=(OWNRT_TP_PERSISTENT_THREAD=1) ;;
    ep) envs+=(OWNRT_TP_EXPERT_PAIR=1) ;;
    rd) envs+=(OWNRT_RETIRE_DEFERRED=1) ;;
    rd=*) envs+=(OWNRT_RETIRE_DEFERRED=${x#rd=}) ;;
    gp0) lenv+=(OWNRT_GDN_PREP=0) ;;
    lenv=*) v=${x#lenv=}; lenv+=("${v//+/,}") ;;
    batched) if [ "$rank" = 1 ]; then more+=(--batched --rows 256); else tmp=(); for y in "${more[@]}"; do [ "$y" = --token-prompt ] || tmp+=("$y"); done; more=("${tmp[@]}" --rows 256); fi ;;
    sp=*) more+=(--second-prompt "${x#sp=}") ;;
    nw) [ "$rank" = 0 ] || halt "nw is rank 0 only"; envs+=(OWNRT_SNAPSHOT_NOWAIT=1 OWNRT_ROLLBACK_NOWAIT=1) ;;
    trace) [ "${#tp[@]}" = 0 ] || halt "trace with --tp is refused (profiler under TP)"; envs+=(OWNRT_SITE_TRACE=1); launch=trace ;;
    "") ;; *) halt "unknown extra $x" ;; esac; done
  L="$D/launch/rank$rank-$launch.json"; [ "${#lenv[@]}" = 0 ] || L="$D/launch/rank$rank-$launch-$name.json"
  python3 - "$PS/rank$rank-launch-c65536-b51c9e8d803e.json" "$BIN" "$launch" "$L" "${lenv[@]}" <<'PY' || halt "launch JSON for $name"
import json, sys
src, binary, kind, out = sys.argv[1:5]
d = json.load(open(src)); argv = d['argv']
for kv in sys.argv[5:]:
    k, v = kv.split('=', 1); d['environment'][k] = v; d.setdefault('changes', []).append(f'launch environment {k}={v} (fixed-cost lab)')
i = next(k for k, x in enumerate(argv) if x.endswith('sc117-engine')); argv[i] = binary
if kind == 'trace': argv[argv.index('--timing') + 1] = 'launch'
d['changes'] = d.get('changes', []) + [f'stage-overhead-2026-10-30: binary {binary}' + (', --timing launch (site trace)' if kind == 'trace' else '')]
json.dump(d, open(out, 'w'), indent=1)
PY
  t=$(date +%s)
  if [ "$rank" = 1 ]; then
    env "${envs[@]}" python3 -B "$PS/tp_rank1_driver.py" run --launch "$L" --out "$out" \
      --steps "$steps" --prompt "$prompt" --cache "$CACHE" "${tp[@]}" "${more[@]}"
  else
    env "${envs[@]}" python3 -B "$PS/tp_rank0_driver.py" run --launch "$L" --out "$out" \
      --steps "$steps" --prompt "$prompt" --pattern "$pattern" --cache "$CACHE" "${tp[@]}" "${more[@]}"
  fi
  rc=$?; echo "arm $name rc=$rc after $(( $(date +%s) - t )) s"
  python3 "$D/klog.py" "$PHASE-after-$name" "$t" "$D/logs/kernel-log-$PHASE-after-$name.txt" || halt "kernel log after $name"
  [ "$rc" -eq 0 ] || { tail -30 "$out/rank$rank.log"; cat "$out/rank$rank/failure.txt" 2>/dev/null; halt "arm $name rc=$rc"; }
  x="$out/rank$rank/tp-exchange.json"
  if [ -f "$x" ]; then cat "$x"; echo
    python3 -c "import json,sys;d=json.load(open('$x'));sys.exit(1 if any(c['timeouts'] or c['abort'] for c in d['cards']) else 0)" || halt "exchange timeout/abort in $name"
  fi
  for s in "$out/rank$rank/draft-final-state/draft-head-split-exchange.json" "$out/rank$rank/draft-final-state/draft-gemv-split-exchange.json"; do
    [ -f "$s" ] || continue; cat "$s"; echo
    python3 -c "import json,sys;d=json.load(open('$s'));sys.exit(1 if d['card1_error'] or any(c['timeouts'] or c['abort'] for c in d['cards']) else 0)" || halt "draft split exchange timeout/abort/error in $name"
  done
  c="$out/rank$rank/tp-replicate-compare.json"
  if [ -f "$c" ]; then head -c 300 "$c"; echo
    python3 -c "import json,sys;sys.exit(0 if json.load(open('$c'))['passed'] else 1)" || halt "card 1 differs from card 0 in $name"
  elif [ "${#tp[@]}" != 0 ]; then halt "no tp-replicate-compare.json in $name"; fi
  [ -f "$out/rank$rank/tp-exchange-sites.json" ] && echo "tp-exchange-sites.json $(wc -c <"$out/rank$rank/tp-exchange-sites.json") bytes"
  [ -f "$out/rank$rank/tp-shape-probe.json" ] && cat "$out/rank$rank/tp-shape-probe.json" && echo
  [ -f "$out/rank$rank/site-trace.jsonl" ] && echo "site-trace.jsonl $(wc -l <"$out/rank$rank/site-trace.jsonl") lines"
  python3 -c "
import json,statistics as st;s=json.load(open('$out/summary.json'));h=s.get('spec_ms') or s.get('half_ms') or []
print('half median (3..):',round(st.median(h[2:]),4) if len(h)>3 else None,'draft',round(st.median((s.get('draft_ms') or [0,0,0,0])[2:]),4))"
done
echo "=== phase $PHASE done $(date -Is)"
echo "done $PHASE" >"$D/logs/STATUS"
