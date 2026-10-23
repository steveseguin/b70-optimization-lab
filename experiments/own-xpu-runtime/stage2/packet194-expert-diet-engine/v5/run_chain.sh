#!/usr/bin/bash
# Packet194 CPU gate chain (serial; each step under nice -n 19 on cores 8-15,24-31; never a device). Writes chain.log.
set -u
cd /home/steve/llm-optimizations || exit 1
V5=experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/v5
rm -f $V5/evidence/chain.log
for s in "$@"; do
  nice -n 19 taskset -c 8-15,24-31 python3 -B $V5/$s.py </dev/null > $V5/evidence/qualify-$s.log 2>&1; rc=$?
  echo "$s rc=$rc" >> $V5/evidence/chain.log
  [ $rc -ne 0 ] && { echo CHAIN-FAILED >> $V5/evidence/chain.log; exit 1; }
done
echo CHAIN-DONE >> $V5/evidence/chain.log
