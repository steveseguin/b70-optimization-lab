#!/bin/bash
# xw92: after tg92, the OWN_XWAIT diagnostic build of the tested src92 snapshot (never a production binary), then
# one short six-card plain run (prompt 1, 48 tokens) recording who waits for whom in each one-token exchange.
set -u
W=/home/steve/dsv41-work
D=$W/runs/xw92; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
until grep -qE "ALLDONE|STOP" $W/runs/tg92/summary.txt 2>/dev/null; do sleep 20; done
until [ ! -e $W/six.active ]; do sleep 5; done
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp92x.log; t0=$(date +%s)
F="-fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -DOWN41_XWAIT"
(cd $W/src92 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp92x -lze_loader > $L 2>&1)
rc=$?; echo "tp92x build exit $rc in $(( $(date +%s) - t0 )) s" >> $L; tail -1 $L >> $sum
[ $rc -eq 0 ] || exit 1
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null; do sleep 10; done
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
P=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
for k in plain xw; do
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  if [ $k = xw ]; then X="OWN_XWAIT=$D/xw.txt"; B=tp92x; else X=""; B=tp92; fi
  env $PL $X OWN_PROMPT=$P OWN_EOS=-1 $W/own_run_v41_$B - 64 $D/$k-ids.txt 4096 > $D/$k.log 2>&1
  echo "$k exit $?" >> $sum; grep -h "decode:\|rror" $D/$k.log | sed "s/^/$k: /" >> $sum
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "FAULT: $f" >> $sum; echo STOP_FAULT >> $sum; exit 1; }
done
cmp -s $D/plain-ids.txt $D/xw-ids.txt && echo "xw IDS_SAME" >> $sum || echo "xw IDS_DIFFER" >> $sum
echo ALLDONE >> $sum
