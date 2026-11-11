#!/bin/bash
# tp99 build (tp98 + wa-1 (OWN_ATT_WA, attention launch does WindowAppendM in checks of 2-8) + xll-1 (OWN_XLL, OWN_XLL_QUICK: one-trip pulls), opt-in): snapshot, syntax check, the engine.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp99.log
[ -e $W/six.active ] && { echo "tp99 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp99; trap 'rm -f $W/locks/build-tp99' EXIT  # GPU runs wait while a build runs
rm -rf $W/src99; mkdir -p $W/src99/tools
cp -a $E/src $E/planning $W/src99/ && cp -a $E/tools/bench $W/src99/tools/
t0=$(date +%s)
F="-fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src99 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp99 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp99 -lze_loader >> $L 2>&1
rc=$?
echo "tp99 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
