#!/bin/bash
# tp98 build (tp97 + qb-off-3 (OWN_QB_OFF_M fix) + dride-1 (OWN_MT_DRIDE), opt-in): snapshot the repo sources into src98, syntax check, the engine.
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp98.log
[ -e $W/six.active ] && { echo "tp98 build exit 9 (six.active present)" >> $L; exit 9; }
touch $W/locks/build-tp98; trap 'rm -f $W/locks/build-tp98' EXIT  # GPU runs wait while a build runs
rm -rf $W/src98; mkdir -p $W/src98/tools
cp -a $E/src $E/planning $W/src98/ && cp -a $E/tools/bench $W/src98/tools/
t0=$(date +%s)
F="-fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
cd $W/src98 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp > $L 2>&1 || {
  echo "tp98 build exit 8 (syntax) in $(( $(date +%s) - t0 )) s" >> $L; exit 8; }
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp98 -lze_loader >> $L 2>&1
rc=$?
echo "tp98 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
