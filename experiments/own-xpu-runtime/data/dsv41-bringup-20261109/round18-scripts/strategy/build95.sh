#!/bin/bash
# tp95 build (tp93 + defaults: thresholds 4, SKNORM=15, HCPP=1; + attn-a1 (OWN_ATT_T) + ck (OWN_MT_CK) + qb-off-1 (OWN_QB_OFF), opt-in): snapshot the repo sources into src95, syntax check, the engine.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp95.log
[ -e $W/six.active ] && { echo "tp95 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp95; trap 'rm -f $W/locks/build-tp95' EXIT  # GPU runs wait while a build runs
rm -rf $W/src95; mkdir -p $W/src95/tools
cp -a $E/src $E/planning $W/src95/ && cp -a $E/tools/bench $W/src95/tools/
t0=$(date +%s)
F="-fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src95 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp95 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp95 -lze_loader >> $L 2>&1
rc=$?
echo "tp95 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
