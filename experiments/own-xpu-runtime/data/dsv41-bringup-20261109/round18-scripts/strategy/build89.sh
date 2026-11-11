#!/bin/bash
# tp89 build: snapshot the repo sources into src89 (the build reads only the snapshot), syntax check, then build
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
[ -e $W/six.active ] && { echo "tp89 build exit 9 (six.active present)" >> $W/build-tp89.log; exit 9; }
rm -rf $W/src89; mkdir -p $W/src89
cp -a $E/src $E/planning $W/src89/
t0=$(date +%s)
F="-fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I planning/dsv41-fixtures -I src"
cd $W/src89 && icpx $F -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $W/build-tp89.log 2>&1 || {
  echo "tp89 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $W/build-tp89.log; exit 8; }
icpx $F -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp89 -lze_loader >> $W/build-tp89.log 2>&1
echo "tp89 build exit $? in $(( $(date +%s) - t0 )) s" >> $W/build-tp89.log
