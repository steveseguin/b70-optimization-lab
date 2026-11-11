#!/bin/bash
# d2: EU stall sampling of the engine forms (bench_dense_m16 PCS=1) on card 0000:23 (ZE_AFFINITY_MASK=1); run as root
# only to read the counters (/proc/sys/dev/xe/observation_paranoid is 1; nothing on the host is changed)
cd /home/steve/dsv41-work; mkdir -p runs/d2
timeout 300 sudo -S env LD_LIBRARY_PATH=/opt/intel/oneapi/pti/latest/lib:/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZE_AFFINITY_MASK=1 PCS=1 /home/steve/dsv41-work/bench_dense_m16 < /home/steve/SUDO_PASSWORD.txt > runs/d2/out.txt 2> runs/d2/err.txt
sudo -k
