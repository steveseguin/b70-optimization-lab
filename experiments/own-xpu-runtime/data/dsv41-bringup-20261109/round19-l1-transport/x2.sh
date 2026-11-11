#!/bin/bash
# L1 step 3: work-group sweep, six-card all-gather, push vs pull, today's IPC contexts
cd /home/steve/dsv41-work/l1
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
E="ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 NEOReadDebugKeys=1 DisableIndirectAccess=1 EnableDeferBacking=0"
T0=$(date '+%Y-%m-%d %H:%M:%S')
J='PCIe Bus Error|AER:|Hardware Error|Machine check|xe .*(fault|reset|hang|timeout)|GuC.*(fail|reset)'
for g in 1 2 4 8 16; do
  env $E ./xchg_direct_bench --ctx=ipc --topos=a2a,pair --forms=fresh --sizes=3456,7296,9728 --wg=$g --reps=5 > x2_g$g.txt 2>&1; rc=$?
  echo "exit $rc" >> x2_g$g.txt
  if journalctl -k --since "$T0" -o cat | grep -E "$J" > x2_faults.txt; then echo FAULT; exit 9; fi
  [ $rc -ne 0 ] && exit $rc
done
echo DONE > x2_done.txt
