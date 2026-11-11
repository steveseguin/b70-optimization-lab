#!/bin/bash
cd /home/steve/dsv41-work/gs
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
T0=$(date '+%Y-%m-%d %H:%M:%S')
J='PCIe Bus Error|AER:|Hardware Error|Machine check|xe .*(fault|reset|hang|timeout)|GuC.*(fail|reset)'
for c in 3 4; do
  ONEAPI_DEVICE_SELECTOR=level_zero:$c ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 NEOReadDebugKeys=1 DisableIndirectAccess=1 ./bench_grf_switch > out_c$c.txt 2>&1; echo "exit $?" >> out_c$c.txt
  journalctl -k --since "$T0" -o cat | grep -E "$J" > faults.txt && { echo FAULT; exit 9; }
done
echo DONE > done.txt
