#!/bin/bash
# tl85: where the plain step's 1.1 ms of idle time goes. tp85 = tp84 + the timeline patch (OWN_TIMELINE; off = no change).
# Short six-card runs on prompt 1 (36 tokens): tp85 plain (answers must equal tp84's), tp85 with the timeline over
# answer steps 20-27 (profiling on), tp84 plain; then the analysis.
set -u
W=/home/steve/dsv41-work; D=$W/runs/tl85; mkdir -p $D; sum=$D/summary.txt
until grep -q "build exit" $W/build-tp85.log 2>/dev/null; do sleep 10; done
grep -q "build exit 0" $W/build-tp85.log || { echo STOP_BUILD >> $sum; exit 1; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
$W/run_exp.sh tl85 tp85 "p85|$PL|speed" "t85|$PL OWN_TIMELINE=$D/tl.txt OWN_TIMELINE_STEPS=20-27|speed"
sed -i '/^DONE$/d' $sum
$W/run_exp.sh tl85 tp84 "p84|$PL|speed"
cd /home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
python3 -I tools/perf/dsv41_timeline.py $D/tl.txt > $D/analysis.txt 2>&1
echo "analysis exit $?" >> $sum
echo ALLDONE >> $sum
