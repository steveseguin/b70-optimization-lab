#!/bin/bash
# tp111 build (tp110 + idxsplit-1 OWN_IDX_SPLIT default 1): snapshot, syntax check, the engine.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp111.log
[ -e $W/six.active ] && { echo "tp111 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp111; trap "rm -f $W/locks/build-tp111" EXIT  # six-card gates wait while a build runs
rm -rf $W/src111; mkdir -p $W/src111/tools
cp -a $E/src $E/planning $W/src111/ && cp -a $E/tools/bench $W/src111/tools/
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src111 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp111 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp111 -lze_loader >> $L 2>&1
rc=$?
echo "tp111 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
