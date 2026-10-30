#!/usr/bin/env bash
# Dump comparisons of one device phase (research/tp/prefill-host-2026-10-30; copy of ctx131072-2026-10-29), CPU only.
# A run name with a leading / is an absolute run directory (for example an archived run of the previous binary).
# Usage: compare_phase.sh PHASE RUNS_DIR "rank:A:B" ... (bitwise: rank 1 tp_rank1_driver.py compare, rank 0 tp_rank0_driver.py compare)
#        "xrank:SMALL:LARGE" ... (cross-context: xctx_compare.py RANK SMALL LARGE; SMALL at 65536, LARGE at 131072)
# Appends every result to logs/PHASE-compare.txt; exit 1 if any comparison differs.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-host-2026-10-30
SR=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/service-ready-2026-10-29
PHASE=$1; RUNS=$2; shift 2; out="$D/logs/$PHASE-compare.txt"; bad=0
echo "# $PHASE compares at $(date -Is) (runs $RUNS)" >>"$out"
for c in "$@"; do
  IFS=: read -r rank a b <<<"$c"
  pa="$RUNS/$a"; pb="$RUNS/$b"; [[ "$a" == /* ]] && pa=$a; [[ "$b" == /* ]] && pb=$b
  if [[ "$rank" == x* ]]; then r=$(python3 -B "$D/xctx_compare.py" "${rank#x}" "$pa" "$pb"); rc=$?
  elif [ "$rank" = 1 ]; then r=$(python3 -B "$D/tp_rank1_driver.py" compare "$pa" "$pb"); rc=$?
  else r=$(python3 -B "$D/tp_rank0_driver.py" compare "$pa" "$pb"); rc=$?; fi
  echo "rank$rank $a vs $b: $r" | tee -a "$out"; [ "$rc" -eq 0 ] || bad=1
done
echo "# $PHASE compares: $([ $bad = 0 ] && echo all equal || echo DIFFER)" | tee -a "$out"
exit $bad
