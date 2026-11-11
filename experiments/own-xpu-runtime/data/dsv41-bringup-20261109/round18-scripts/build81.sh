#!/bin/bash
W=/home/steve/dsv41-work; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
t0=$(date +%s)
cd $W/src81 && icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I planning/dsv41-fixtures -I src planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp81 -lze_loader > $W/build-tp81.log 2>&1
echo "tp81 build exit $? in $(( $(date +%s) - t0 )) s" >> $W/build-tp81.log
