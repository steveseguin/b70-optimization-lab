#!/bin/bash
# pcs1: EU stall samples of production IQ2_XXS gate+up vs the packed-lane forms (bench_routed_m1 -DOWN_PCS) on card 1;
# root only to read the counters (observation_paranoid stays 1; nothing on the host is changed)
cd /home/steve/dsv41-work/kb
timeout 300 sudo -S env LD_LIBRARY_PATH=/opt/intel/oneapi/pti/latest/lib:/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZE_AFFINITY_MASK=3 /home/steve/dsv41-work/kb/bench_routed_pcs < /home/steve/SUDO_PASSWORD.txt > pcs1b/out.txt 2> pcs1b/err.txt
echo "exit $?" >> pcs1b/out.txt
sudo -k
