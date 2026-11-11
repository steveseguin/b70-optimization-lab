#!/bin/bash
# L1 step 1: shared native context host-RAM probe (small, safety-stopped), one process at a time
cd /home/steve/dsv41-work/l1
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
E="ZE_ENABLE_PCI_ID_DEVICE_ORDER=1"
T0=$(date '+%Y-%m-%d %H:%M:%S')
J='PCIe Bus Error|AER:|Hardware Error|Machine check|xe .*(fault|reset|hang|timeout)|GuC.*(fail|reset)'
run() { tag=$1; shift; echo "=== $tag: $*"; env $E "$@" > p1_$tag.txt 2>&1; echo "exit $?" >> p1_$tag.txt; tail -3 p1_$tag.txt
  if journalctl -k --since "$T0" -o cat | grep -E "$J" > p1_faults.txt; then echo FAULT; cat p1_faults.txt; exit 9; fi; }
run a_shared2   env NEOReadDebugKeys=1 EnableDeferBacking=0 ./probe_shared_ctx_ram shared 2 1024 256
run b_percard2  env NEOReadDebugKeys=1 EnableDeferBacking=0 ./probe_shared_ctx_ram percard 2 1024 256
run c_resident2 env NEOReadDebugKeys=1 EnableDeferBacking=0 ./probe_shared_ctx_ram shared 2 1024 256 --peer-resident
run d_shared6   env NEOReadDebugKeys=1 EnableDeferBacking=0 ./probe_shared_ctx_ram shared 6 1024 256 --peer-touch
run e_default2  ./probe_shared_ctx_ram shared 2 1024 256
echo DONE > p1_done.txt
