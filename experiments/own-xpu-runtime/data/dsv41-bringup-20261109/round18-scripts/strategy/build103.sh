#!/bin/bash
# tp103 build (tp102 + px-1b (the halves' router base) + OWN_TIMELINE_PROMPT + xperm-3 compiled in (-DOWN_R2_TAB_COPY_XXS=1) + G128 / pace-1 default (+ pace-2 if it lands)): snapshot, syntax check, the engine.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp103.log
[ -e $W/six.active ] && { echo "tp103 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp103; trap "rm -f $W/locks/build-tp103" EXIT  # six-card gates wait while a build runs
rm -rf $W/src103; mkdir -p $W/src103/tools
cp -a $E/src $E/planning $W/src103/ && cp -a $E/tools/bench $W/src103/tools/
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src103 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp103 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp103 -lze_loader >> $L 2>&1
rc=$?
echo "tp103 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
