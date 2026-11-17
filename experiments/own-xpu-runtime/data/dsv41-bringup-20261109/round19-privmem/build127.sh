#!/bin/bash
# tp127 build (2026-11-17 01:1x): tp126 + hostfloor-2 (a host-memory dip during the upload pauses the copies) + idxbc-1 on
# by default (the R-row index scores by sub-group broadcast; bench PASS, -18..-21 %), 84453b5c74 (+ hl232: prompt heads 3,3,2,3,3,2 by default)
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp127.log
touch $W/locks/build-tp127; trap "rm -f $W/locks/build-tp127" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
# each candidate commit: export, syntax check, device build; the first that builds wins
while [ -e $W/six.active ]; do sleep 20; done
: > $L
rc=8
for C in 84453b5c74; do
  rm -rf $W/src127; mkdir -p $W/src127/tools
  git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src127 || { echo "tp127 build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src127 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp127: syntax check failed at $C" >> $L; continue; fi
  echo "tp127: source commit $C" >> $L
  (cd $W/src127 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp127 -lze_loader >> $L 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    for b in; do
      (cd $W/src127 && nice -n 5 icpx -fsycl $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/${b%%:*}.cpp -o $W/${b##*:} >> $L 2>&1) \
        && echo "tp127: bench ${b##*:} built" >> $L || echo "tp127: bench ${b##*:} FAILED" >> $L
    done
    break
  fi
  echo "tp127: device build failed at $C (exit $rc)" >> $L
done
echo "tp127 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
