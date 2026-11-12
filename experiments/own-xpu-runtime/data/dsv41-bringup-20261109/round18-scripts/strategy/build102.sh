#!/bin/bash
# tp102 build (tp101 + draft slots padded to 128 B + pace-1 (OWN_MT_PACE, opt-in) + pb-1 and wa-2 as defaults; px-1 (OWN_PX, opt-in) + xperm-2 compiled in): snapshot, syntax check, the engine.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp102.log
[ -e $W/six.active ] && { echo "tp102 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp102; trap 'rm -f $W/locks/build-tp102' EXIT  # GPU runs wait while a build runs
rm -rf $W/src102; mkdir -p $W/src102/tools
cp -a $E/src $E/planning $W/src102/ && cp -a $E/tools/bench $W/src102/tools/
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src102 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp102 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp102 -lze_loader >> $L 2>&1
rc=$?
echo "tp102 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
