#!/bin/bash
# tp100 build (tp99 + qb-off compiled out by default (OWN41_QBOFF_M) + xperm-1 (OWN_PAIR_G128) + wa-2 (OWN_ATT_WA=2) + pb-1 (OWN_PB), opt-in; xll banned): snapshot, syntax check, the engine.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp100.log
[ -e $W/six.active ] && { echo "tp100 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp100; trap 'rm -f $W/locks/build-tp100' EXIT  # GPU runs wait while a build runs
rm -rf $W/src100; mkdir -p $W/src100/tools
cp -a $E/src $E/planning $W/src100/ && cp -a $E/tools/bench $W/src100/tools/
t0=$(date +%s)
F="-fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src100 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp100 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp100 -lze_loader >> $L 2>&1
rc=$?
echo "tp100 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
