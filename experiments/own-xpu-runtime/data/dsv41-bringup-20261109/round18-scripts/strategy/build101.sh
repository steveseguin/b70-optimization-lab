#!/bin/bash
# tp101 build (tp100 + xperm-2 compiled in: -DOWN_R2_TAB_COPY=1, routed grid tables copied from a constant image): snapshot, syntax check, the engine.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp101.log
[ -e $W/six.active ] && { echo "tp101 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp101; trap 'rm -f $W/locks/build-tp101' EXIT  # GPU runs wait while a build runs
rm -rf $W/src101; mkdir -p $W/src101/tools
cp -a $E/src $E/planning $W/src101/ && cp -a $E/tools/bench $W/src101/tools/
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src101 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp101 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp101 -lze_loader >> $L 2>&1
rc=$?
echo "tp101 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
