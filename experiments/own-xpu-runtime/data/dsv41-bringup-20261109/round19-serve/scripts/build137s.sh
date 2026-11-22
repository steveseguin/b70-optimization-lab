#!/bin/bash
# tp137s build (2026-11-17): 267262e9db (the tp136 source: serve-1 + reset-1 + uppar-1 + klazy-1) compiled with
# -fsycl-device-code-split=per_kernel: one image per kernel, so with OWN_PREBUILD=0 only launched kernels load (host memory).
W=/home/steve/dsv41-work
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp137s.log
touch $W/locks/build-tp137s; trap "rm -f $W/locks/build-tp137s" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
while [ -e $W/six.active ] || [ -e $W/HOLD_BUILDS ]; do sleep 20; done
until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 8 ]; do sleep 20; done
: > $L
C=267262e9db
rm -rf $W/src137; mkdir -p $W/src137/tools
git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src137 || { echo "tp137s build exit 9 (source export $C)" >> $L; exit 9; }
if ! (cd $W/src137 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
  echo "tp137s: syntax check failed at $C" >> $L; echo "tp137s build exit 7" >> $L; exit 7; fi
echo "tp137s: source commit $C (serve-1 + reset-1 + uppar-1 + klazy-1; split per kernel)" >> $L
(cd $W/src137 && timeout 14400 nice -n 5 icpx $F -fsycl-device-code-split=per_kernel -fsycl-max-parallel-link-jobs=3 -I planning/dsv41-fixtures -I src $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp137s -lze_loader >> $L 2>&1)
rc=$?
echo "tp137s build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
[ $rc -eq 0 ] && echo "tp137s binary: $(ls -la $W/own_run_v41_tp137s | awk '{print $5}') bytes; offload bundle $(readelf -S -W $W/own_run_v41_tp137s | awk '$2 ~ /OFFLOAD/ {print strtonum("0x"$6)}') bytes" >> $L
exit $rc
