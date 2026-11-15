#!/bin/bash
# tp114 build (tp113 543b796ca + idxsplit-3 (OWN_IDX_DSPLIT, opt-in) + skip39-1 (OWN_SKIP39, opt-in); sources: worktree tp114src, patch tp114-vs-543b796ca.patch): snapshot, syntax check, the engine.
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp114.log
[ -e $W/six.active ] && { echo "tp114 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp114; trap "rm -f $W/locks/build-tp114" EXIT  # six-card gates wait while a build runs
rm -rf $W/src114; mkdir -p $W/src114/tools
cp -a $E/src $E/planning $W/src114/ && cp -a $E/tools/bench $W/src114/tools/
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src114 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp114 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp114 -lze_loader >> $L 2>&1
rc=$?
echo "tp114 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
