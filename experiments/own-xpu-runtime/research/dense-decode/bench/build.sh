#!/bin/bash
# usage: build.sh src.cpp out
cd /dev/shm/ownrt-lab-dense/work
nice -n 19 taskset -c 8-15,24-31 /opt/intel/oneapi/compiler/2026.0/bin/icpx -std=gnu++20 -O2 -g0 -DP56X_SLEEP20=0 -Werror=return-type -fno-fast-math -ffp-contract=off -ffunction-sections -fdata-sections -fsycl -fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt -I /dev/shm/ownrt-lab-dense/engine/src -I . $1 -o $2 -fsycl -Wl,--gc-sections -lze_loader 2>&1 | grep -E "error" -A4 | head -30
