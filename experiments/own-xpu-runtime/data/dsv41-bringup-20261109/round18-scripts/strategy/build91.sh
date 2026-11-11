#!/bin/bash
# tp91 build: snapshot the repo sources into src91 (the build reads only the snapshot), syntax check, the engine,
# then pcd-1's two test programs (six-card exchange test, one-card bench) from the same snapshot.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp91.log
[ -e $W/six.active ] && { echo "tp91 build exit 9 (six.active present)" >> $L; exit 9; }
rm -rf $W/src91; mkdir -p $W/src91/tools
cp -a $E/src $E/planning $W/src91/ && cp -a $E/tools/bench $W/src91/tools/
t0=$(date +%s)
F="-fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src91 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp91 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp91 -lze_loader >> $L 2>&1
rc=$?
nice -n 5 icpx $F $GPU "-options -ze-intel-enable-auto-large-GRF-mode" -I src tools/bench/xchg_pull2_test.cpp -o $W/pcd/xchg_pull2_test -lze_loader > $W/pcd/build-xtest.log 2>&1
echo "xtest build exit $?" >> $L
nice -n 5 icpx $F $GPU "-options -ze-intel-enable-auto-large-GRF-mode" -I src -I tools/bench tools/bench/bench_dsplit.cpp -o $W/pcd/bench_dsplit > $W/pcd/build-bench.log 2>&1
echo "bench build exit $?" >> $L
echo "tp91 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
