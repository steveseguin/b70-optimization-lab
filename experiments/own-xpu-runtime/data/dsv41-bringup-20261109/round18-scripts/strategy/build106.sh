#!/bin/bash
# tp106 build (tp105 + ck2-1 (OWN_CK2, opt-in: 2-3-token check forms) + defaults OWN_FL=3, OWN_U3_NOPAIR=1 + OWN_MT_EU_HEAVY=0 (tg105h)): snapshot, syntax check, the engine.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp106.log
[ -e $W/six.active ] && { echo "tp106 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp106; trap "rm -f $W/locks/build-tp106" EXIT  # six-card gates wait while a build runs
rm -rf $W/src106; mkdir -p $W/src106/tools
cp -a $E/src $E/planning $W/src106/ && cp -a $E/tools/bench $W/src106/tools/
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src106 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp106 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp106 -lze_loader >> $L 2>&1
rc=$?
echo "tp106 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
