#!/usr/bin/env bash
# Bitwise comparisons of rank-harness runs (CPU only; copy of fixed-cost-2-2026-10-30/compare.sh for hc-split-2026-10-30): the prefill-speed rank drivers' own `compare` (full state.json
# buffer hashes, tokens, rank 0 draft buffers and draft tokens, the second request of --second-prompt runs and the
# The ones invariant uses the exact-pattern checker of research/tp/prefill-draft-batch-2026-10-30 (compare_driver.py).
# reset inventories). Usage: compare.sh PHASE RUNS_DIR "rank:A:B" ...  Appends to logs/PHASE-compare.txt; exit 1 if any differs.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/hc-split-2026-10-30
PS=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-speed-2026-10-29
PD=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-draft-batch-2026-10-30
PHASE=$1; RUNS=$2; shift 2; out="$D/logs/$PHASE-compare.txt"; bad=0
echo "# $PHASE compares at $(date -Is) (runs $RUNS)" >>"$out"
for c in "$@"; do
  IFS=: read -r rank a b <<<"$c"
  pa="$RUNS/$a"; pb="$RUNS/$b"; [[ "$a" == /* ]] && pa=$a; [[ "$b" == /* ]] && pb=$b
  if [ "$rank" = 1 ]; then r=$(python3 -B "$D/compare_driver.py" "$D/drivers/tp_rank1_driver.py" compare "$pa" "$pb"); rc=$?
  else r=$(python3 -B "$D/compare_driver.py" "$PD/tp_rank0_driver.py" compare "$pa" "$pb"); rc=$?; fi
  t=$(python3 -c "
import json,sys
A=json.load(open('$pa/summary.json'));B=json.load(open('$pb/summary.json'))
k=[x for x in ('tokens','draft_tokens','guesses') if x in A or x in B]
eq={x:A.get(x)==B.get(x) for x in k};n={x:len(A.get(x) or []) for x in k}
print(json.dumps(dict(summary_equal=eq,counts=n)));sys.exit(0 if all(eq.values()) else 1)"); trc=$?
  echo "rank$rank $a vs $b: rc=$rc $r | summary rc=$trc $t" | tee -a "$out"; [ "$rc" -eq 0 ] && [ "$trc" -eq 0 ] || bad=1
done
echo "# $PHASE compares: $([ $bad = 0 ] && echo all equal || echo DIFFER)" | tee -a "$out"
exit $bad
