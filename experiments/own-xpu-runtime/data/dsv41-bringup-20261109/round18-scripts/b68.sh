#!/bin/bash
# build tp68 (defaults: split heads for blocks of >= 16, 4-row blocks at 16; OWN_IDX_R, OWN_XPULL_LB options), then e82
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
cd /home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
t0=$(date +%s)
icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I planning/dsv41-fixtures -I src planning/dsv41-fixtures/own_run_v41.cpp -o $S/own_run_v41_tp68 -lze_loader > $S/build-tp68.log 2>&1
rc=$?
echo "tp68 build exit $rc in $(( $(date +%s) - t0 )) s" > $S/build-tp68.status
[ $rc -eq 0 ] || exit 1
IR=4 $S/e82.sh
