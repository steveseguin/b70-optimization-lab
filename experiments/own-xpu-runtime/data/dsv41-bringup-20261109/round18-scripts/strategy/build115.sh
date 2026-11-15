#!/bin/bash
# tp115 build (tp114 sources + defaults: OWN_PX_SERIAL=1 (stable mode), OWN_SKIP39=1, OWN_IDX_DSPLIT=3; worktree tp114src commit f1ba86644, patch tp115-vs-543b796ca.patch). Run by c115.sh, which holds six.active.
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp115.log
touch $W/locks/build-tp115; trap "rm -f $W/locks/build-tp115" EXIT  # six-card gates wait while a build runs
rm -rf $W/src115; mkdir -p $W/src115/tools
cp -a $E/src $E/planning $W/src115/ && cp -a $E/tools/bench $W/src115/tools/
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src115 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp115 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp115 -lze_loader >> $L 2>&1
rc=$?
echo "tp115 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
