#!/bin/bash
# tp105 build (tp104 + fl-1 (OWN_FL, opt-in) + xperm-4 (xorP compiled in: -DOWN_R2_XORP=1; OWN_U3_NOPAIR opt-in) + sw (OWN_MT_SW, opt-in)): snapshot, syntax check, the engine.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp105.log
[ -e $W/six.active ] && { echo "tp105 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp105; trap "rm -f $W/locks/build-tp105" EXIT  # six-card gates wait while a build runs
rm -rf $W/src105; mkdir -p $W/src105/tools
cp -a $E/src $E/planning $W/src105/ && cp -a $E/tools/bench $W/src105/tools/
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src105 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp105 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp105 -lze_loader >> $L 2>&1
rc=$?
echo "tp105 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
