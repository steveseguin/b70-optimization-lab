#!/bin/bash
# t136k (klazy-1: OWN_PREBUILD=0) <max_ctx> <up_par> [long cases]: tp136 serve tests (phase reset) with OWN_UP_PAR, host memory sampled every
# 0.25 s and the engine's per-card driver memory every 2 s.
M=${1:-994304}; UP=${2:-2}; LC=${3:-x34k,x200k}
D=/home/steve/dsv41-serve/tests/out136k-$M-up$UP; mkdir -p $D
/home/steve/dsv41-serve/preflight-serve.sh > $D/preflight.txt 2>&1 || { echo "preflight failed" >> $D/summary.txt; sync; exit 1; }
( while sleep 5; do sync; done ) & SY=$!
/home/steve/dsv41-serve/tests/memsample.sh $D/mem.txt 2400 & MS=$!
trap 'kill $SY $MS 2>/dev/null; rm -f /home/steve/dsv41-work/six.active; sync' EXIT
B=/home/steve/dsv41-work/own_run_v41_tp136
OWN_PREBUILD=0 OWN_UP_PAR=$UP /home/steve/dsv41-serve/venv/bin/python -I -u /home/steve/dsv41-serve/tests/t_engine.py $B $M reset $D $LC >> $D/summary.txt 2>&1
echo "t_engine exit $?" >> $D/summary.txt
