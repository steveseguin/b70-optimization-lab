#!/bin/bash
# L1 step 2: direct peer-store exchange bench (smoke pair, six cards shared, six cards IPC control)
cd /home/steve/dsv41-work/l1
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
E="ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 NEOReadDebugKeys=1 DisableIndirectAccess=1 EnableDeferBacking=0"
T0=$(date '+%Y-%m-%d %H:%M:%S')
J='PCIe Bus Error|AER:|Hardware Error|Machine check|xe .*(fault|reset|hang|timeout)|GuC.*(fail|reset)'
run() { tag=$1; shift; echo "=== $tag: $*"; env $E "$@" > x1_$tag.txt 2>&1; rc=$?; echo "exit $rc" >> x1_$tag.txt; tail -3 x1_$tag.txt
  if journalctl -k --since "$T0" -o cat | grep -E "$J" > x1_faults.txt; then echo FAULT; cat x1_faults.txt; exit 9; fi
  [ $rc -ne 0 ] && { echo "nonzero exit, stopping"; exit $rc; }; }
run a_smoke ./xchg_direct_bench --cards=0,1 --topos=pair --forms=persist --sizes=3456 --reps=3
run b_six ./xchg_direct_bench
run c_ipc ./xchg_direct_bench --ctx=ipc
echo DONE > x1_done.txt
