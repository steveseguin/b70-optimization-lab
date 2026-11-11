#!/bin/bash
# u1: EU stall sampling of the expert kernels (test_routed_u PCS=1, formats IQ2_XXS and IQ2_S: the engine's
# routed experts) on card 0000:23 (ZE_AFFINITY_MASK=1, card argument 0); root only to read the counters
cd /home/steve/dsv41-work; mkdir -p runs/u1
timeout 600 sudo -S env LD_LIBRARY_PATH=/opt/intel/oneapi/pti/latest/lib:/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZE_AFFINITY_MASK=1 PCS=1 ONLY=xxs,iq2s /home/steve/dsv41-work/test_routed_u_pcs 0 < /home/steve/SUDO_PASSWORD.txt > runs/u1/out.txt 2> runs/u1/err.txt
echo "rc=$?" >> runs/u1/out.txt
sudo -k
