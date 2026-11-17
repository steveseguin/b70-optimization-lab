#!/bin/bash
# tp132 build (2026-11-17): 0c13b65e7e = f85cac083c (pb-2, opt-in) + obpad-1 (OWN_OB_PAD, opt-in: the block's
# q / attention-output / head-output rows qh * hd + pad floats apart per token, not 128 KiB) + ifldiag-1c (the
# check-site diagnostic from the marks, and the pulled block candidates pass 1 vs pass 2). Then the obpad bench
# (densews/bench_r4.cpp with -DNO_R4: today's picks only; output-a at the packed, 128 KiB and padded strides).
W=/home/steve/dsv41-work
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp132.log
touch $W/locks/build-tp132; trap "rm -f $W/locks/build-tp132" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
while [ -e $W/six.active ] || [ -e $W/HOLD_BUILDS ]; do sleep 20; done
until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ]; do sleep 20; done
: > $L
rc=8
for C in 0c13b65e7e; do
  rm -rf $W/src132; mkdir -p $W/src132/tools
  git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src132 || { echo "tp132 build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src132 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp132: syntax check failed at $C" >> $L; continue; fi
  echo "tp132: source commit $C" >> $L
  (cd $W/src132 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp132 -lze_loader >> $L 2>&1)
  rc=$?
  [ $rc -eq 0 ] && break
  echo "tp132: device build failed at $C (exit $rc)" >> $L
done
echo "tp132 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
# obpad bench: output-a at 32,768 / 32,784 / 32,832 / 33,024 floats per token (and packed), today's picks only
if [ -d $W/src132/src ]; then
  DW=$W/densews
  (cd $DW && nice -n 5 icpx -fsycl $GPU '-options -ze-intel-enable-auto-large-GRF-mode' \
    -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -DPART_PICK -DNO_R4 -I $W/src132/src bench_r4.cpp \
    -o bin/bench_obpad > logs/build-obpad.log 2>&1)
  echo "obpad bench build exit $?" >> $L
fi
exit $rc
