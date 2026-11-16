#!/bin/bash
# chainq125 (2026-11-16): after chainq124 (tlp2 -> ckvs2 -> ck1m; its tm1p..ab2p skip on defer-122, touched after chainq124 started): build tp123
# (dtopk-1 default + idxrp-1) -> tsx1 (test_index_score_px + test_dtopk, one card) -> pick the fastest identical
# prompt-score variant at 705K (idxrp-var.txt; none unless >= 3 % faster than IndexerScoreBM) -> c123 -> tm1p, ct1p,
# lp1p, ab2p. A failed preflight or a kernel fault line that is not our own out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
step() { sleep 10; say "starting $1"; bash $W/$1.sh; local s=$(ls -td $W/runs/$1-*/ 2>/dev/null | head -1)summary.txt
  say "$1 ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $1; }
while systemctl --user is-active -q chainq124; do sleep 20; done
rm -f $W/defer-122 $W/idxrp-var.txt
say "chainq125: building tp123"
bash $W/build123.sh
if grep -q "tp123 build exit 0" $W/build-tp123.log; then
  say "tp123 built: $(grep 'source commit\|bench' $W/build-tp123.log | tr '\n' ' ' | cut -c1-300)"
  python3 -I $W/privmem_check.py $W/own_run_v41_tp123 2>&1 | head -3 >> $log
  if [ -x $W/test_index_score_px ] && grep -q "source commit a9a9944a3e" $W/build-tp123.log; then
    step tsx1
    s=$(ls -td $W/runs/tsx1-*/ | head -1)
    python3 -I - ${s}idxpx.log $W/idxrp-var.txt >> $log 2>&1 <<'PY'
import sys
env = ['OWN_IDX_RMAJ=1', 'OWN_IDX_RP=2', 'OWN_IDX_RP=2 OWN_IDX_RMAJ=1', 'OWN_IDX_RP=4', 'OWN_IDX_RP=4 OWN_IDX_RMAJ=1']
txt = open(sys.argv[1]).read()
if 'PASS (' not in txt.splitlines()[-1]:
    print('idxrp: the bench did not PASS: no variant'); sys.exit(0)
for ln in txt.splitlines():
    f = ln.replace('|', ' ').split()
    if len(f) > 9 and f[0] == '1' and f[1] == '705000':
        tb = float(f[2]); vs = []
        for v in range(5):
            x = f[3 + v]
            if x.endswith('!'): continue
            vs.append((float(x), v))
        best = min(vs)
        print('idxrp at 705K: BM %.2f ms, best %s %.2f ms' % (tb, env[best[1]], best[0]))
        if best[0] < 0.97 * tb:
            open(sys.argv[2], 'w').write(env[best[1]])
        break
PY
  else
    say "tsx1 skipped (bench missing or the fallback commit was built)"
  fi
  step c123
else
  say "tp123 build failed: $(grep -E ' error' $W/build-tp123.log | head -3 | tr '\n' ' ' | cut -c1-400)"
fi
for st in tm1p ct1p lp1p ab2p; do step $st; done
say "queue done"
