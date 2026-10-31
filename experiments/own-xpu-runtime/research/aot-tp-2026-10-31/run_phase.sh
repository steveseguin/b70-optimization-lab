#!/usr/bin/env bash
# Device phase of research/aot-tp-2026-10-31 (copy of research/two-card-flags-2026-10-31/run_phase.sh, itself a copy of
# research/tp/hc-split-2026-10-30/run_phase.sh; rank drivers of the prefill-speed-2026-10-29 lineage unchanged; safety checks
# unchanged). Changes: each arm names its binary with the extra `jit` (SO_BIN_JIT, lab build r1 40388fc92c43) or `aot`
# (SO_BIN_AOT, the same tree and flags built with -fsycl-targets=intel_gpu_bmg_g31), so the JIT and AOT arms of one
# configuration run in one phase on one card; each binary has its own SYCL/NEO cache directory (cache-jit, cache-aot under
# $(dirname RUNS)), so after the phase the AOT cache shows whether anything was compiled at run time; runs go to
# /dev/shm/aot-tp-2026-10-31/runs; the per-arm launch JSON is named by its binary. Modes and extras as the two-card-flags
# copy (one, full, ...; B/Bnonw = research/two-card-flags-2026-10-31/flags.py, read in place).
# Launched once as a transient unit that already holds the locks (launch_phase.sh). Do not edit while it runs.
# ARM = name:rank:mode:steps:prompt:pattern:extra   (extra must contain jit or aot)
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/aot-tp-2026-10-31
BDF=${TC_BDF:-0000:43:00.0}
PS=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-speed-2026-10-29
TCF=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/two-card-flags-2026-10-31
PD=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-draft-batch-2026-10-30  # rank-0 driver (records every OWNRT_ key the rank saw)
RUNS=${SO_RUNS:-/dev/shm/aot-tp-2026-10-31/runs}
BIN_JIT=${SO_BIN_JIT:-unset}; BIN_AOT=${SO_BIN_AOT:-unset}
PHASE=$1; shift
exec >>"$D/logs/$PHASE.log" 2>&1
echo "=== phase $PHASE jit $BIN_JIT ($(sha256sum "$BIN_JIT" | cut -c1-12)) aot $BIN_AOT ($(sha256sum "$BIN_AOT" | cut -c1-12)) start $(date -Is) pid $$ affinity $(taskset -pc $$ | sed 's/.*: //') nofile $(ulimit -n)"
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
  launch=default; lenv=(); BIN=; bn=
  for x in ${extra//,/ }; do case "$x" in
    jit) BIN=$BIN_JIT; bn=jit ;;   # aot-tp: the JIT r1 binary
    aot) BIN=$BIN_AOT; bn=aot ;;   # aot-tp: the AOT binary
    xs=*) envs+=(OWNRT_TP_EXCHANGE_STATS=${x#xs=}) ;;
    pt) envs+=(OWNRT_TP_PERSISTENT_THREAD=1) ;;
    ep) envs+=(OWNRT_TP_EXPERT_PAIR=1) ;;
    hk=*) v=${x#hk=}; envs+=(OWNRT_HC_KERNELS=${v//+/,}) ;;
    df=*) v=${x#df=}; envs+=(OWNRT_DRAFT_FAST=${v//+/,}) ;;   # fixed-cost-2: draft-step levers (tokens joined by '+')
    tf=*) v=${x#tf=}; envs+=(OWNRT_TARGET_FAST=${v//+/,}) ;;  # fixed-cost-2: target-side levers (tokens joined by '+')
    f3=*) v=${x#f3=}; envs+=(OWNRT_FAST3=${v//+/,}) ;;        # fixed-cost-3: round-3 levers (tokens joined by '+')
    hs=*) v=${x#hs=}; envs+=(OWNRT_TP_HC_SPLIT=${v//+/,}) ;;   # hc-split: OWNRT_TP_HC_SPLIT (tokens joined by '+')
    ht) envs+=(OWNRT_PREFILL_HOST_TRACE=1) ;;                  # host-phase trace of draft rows (diagnostic, host clock only)
    dc) [ "$rank" = 0 ] || halt "dc is rank 0 only"; envs+=(OWNRT_DRAFT_CHUNK_REPLAY=1); more+=(--draft-chunk) ;;  # draft prompt chunks as one command
    db) envs+=(OWNRT_DRAFT_CHUNK_BATCH=1) ;;                   # prefill-draft-batch-2026-10-30: batched KV-only draft prompt rows
    ph) envs+=(OWNRT_PREFILL_LOOKUP_BATCH=1 OWNRT_PREFILL_MOE_NATIVE=1 OWNRT_PREFILL_XZERO_ONCE=1 OWNRT_DRAFT_CHUNK_REPLAY=1 OWNRT_DRAFT_CHUNK_KV_ONLY=1
            OWNRT_PREFILL_SPECIAL_ROWS=1 OWNRT_PREFILL_LOOKUP_THREADS=4 OWNRT_DRAFT_CHUNK_STAGE_THREAD=1 OWNRT_DRAFT_CHUNK_GUARD_ROW=1 OWNRT_DRAFT_CHUNK_ROW_COPY=1) ;;  # the tptsxqckh prefill flags
    rd) envs+=(OWNRT_RETIRE_DEFERRED=1) ;;
    rd=*) envs+=(OWNRT_RETIRE_DEFERRED=${x#rd=}) ;;
    gp0) lenv+=(OWNRT_GDN_PREP=0) ;;
    lenv=*) v=${x#lenv=}; lenv+=("${v//+/,}") ;;
    batched) if [ "$rank" = 1 ]; then more+=(--batched --rows 256); else tmp=(); for y in "${more[@]}"; do [ "$y" = --token-prompt ] || tmp+=("$y"); done; more=("${tmp[@]}" --rows 256); fi ;;
    sp=*) more+=(--second-prompt "${x#sp=}") ;;
    nw) [ "$rank" = 0 ] || halt "nw is rank 0 only"; envs+=(OWNRT_SNAPSHOT_NOWAIT=1 OWNRT_ROLLBACK_NOWAIT=1) ;;
    trace) [ "${#tp[@]}" = 0 ] || halt "trace with --tp is refused (profiler under TP)"; envs+=(OWNRT_SITE_TRACE=1); launch=trace ;;
    B|Bnonw) part=$([ "$x" = B ] && echo B || echo nonw); while IFS= read -r kv; do envs+=("$kv"); done < <(python3 "$TCF/flags.py" "$part") ;;  # the two-card flag set, read from research/two-card-flags-2026-10-31/flags.py itself
    "") ;; *) halt "unknown extra $x" ;; esac; done
  [ -n "$bn" ] && [ -x "$BIN" ] || halt "arm $name names no binary (extra jit or aot)"
  CACHE=$(dirname "$RUNS")/cache-$bn
  L="$D/launch/rank$rank-$launch-$bn.json"; [ "${#lenv[@]}" = 0 ] || L="$D/launch/rank$rank-$launch-$bn-$name.json"
  python3 - "$PS/rank$rank-launch-c65536-b51c9e8d803e.json" "$BIN" "$launch" "$L" "$BDF" "${lenv[@]}" <<'PY' || halt "launch JSON for $name"
import json, sys
src, binary, kind, out, bdf = sys.argv[1:6]
d = json.load(open(src)); argv = d['argv']
d['environment']['FilterBdfPath'] = bdf; d.setdefault('changes', []).append(f'aot-tp-2026-10-31: one-card arms on {bdf} (--tp pops FilterBdfPath)')
for kv in sys.argv[6:]:
    k, v = kv.split('=', 1); d['environment'][k] = v; d.setdefault('changes', []).append(f'launch environment {k}={v} (fixed-cost lab)')
i = next(k for k, x in enumerate(argv) if x.endswith('sc117-engine')); argv[i] = binary
if kind == 'trace': argv[argv.index('--timing') + 1] = 'launch'
d['changes'] = d.get('changes', []) + [f'stage-overhead-2026-10-30: binary {binary}' + (', --timing launch (site trace)' if kind == 'trace' else '')]
json.dump(d, open(out, 'w'), indent=1)
PY
  t=$(date +%s)
  if [ "$rank" = 1 ]; then
    env "${envs[@]}" python3 -B "$D/drivers/tp_rank1_driver.py" run --launch "$L" --out "$out" \
      --steps "$steps" --prompt "$prompt" --cache "$CACHE" "${tp[@]}" "${more[@]}"
  else
    env "${envs[@]}" python3 -B "$PD/tp_rank0_driver.py" run --launch "$L" --out "$out" \
      --steps "$steps" --prompt "$prompt" --pattern "$pattern" --cache "$CACHE" "${tp[@]}" "${more[@]}"
  fi
  rc=$?; echo "arm $name rc=$rc after $(( $(date +%s) - t )) s; binary $bn; cache-$bn neo files $(find "$CACHE" -type f 2>/dev/null | wc -l)"
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
  find "$out" -name state.bundle -path "*state-*" -delete
  [ -f "$out/rank$rank/hc-kernels.json" ] && cat "$out/rank$rank/hc-kernels.json" && echo
  for j in draft-fast.json target-fast.json fast3.json; do [ -f "$out/rank$rank/$j" ] && cat "$out/rank$rank/$j" && echo; done
  [ -f "$out/rank$rank/tp-hc-split.json" ] && python3 -c "import json;d=json.load(open('$out/rank$rank/tp-hc-split.json'));d.pop('launches');print('tp-hc-split',json.dumps(d))"
  [ -f "$out/rank$rank/decode-fusion.json" ] && echo "decode-fusion $(cat "$out/rank$rank/decode-fusion.json")"
  python3 -c "
import json,statistics as st;s=json.load(open('$out/summary.json'));h=s.get('spec_ms') or s.get('half_ms') or []
print('half median (3..):',round(st.median(h[2:]),4) if len(h)>3 else None,'draft',round(st.median((s.get('draft_ms') or [0,0,0,0])[2:]),4))"
done
echo "=== phase $PHASE done $(date -Is)"
echo "done $PHASE" >"$D/logs/STATUS"
