#!/bin/bash
# tp123 build (2026-11-16): tp121 + dtopk-1 on by default (c715cf7551) + idxrp-1 (a9a9944a3e: OWN_IDX_RP /
# OWN_IDX_RMAJ, the prompt halves' index scores; opt-in). Benches: test_dtopk, test_index_score_px. Falls back to
# c715cf7551 (dtopk default only) if a9a9944a3e does not build. -exclude_ir as tp122.
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp123.log
touch $W/locks/build-tp123; trap "rm -f $W/locks/build-tp123" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
# each candidate commit: export, syntax check, device build; the first that builds wins
while [ -e $W/six.active ]; do sleep 20; done
: > $L
rc=8
for C in a9a9944a3e c715cf7551; do
  rm -rf $W/src123; mkdir -p $W/src123/tools
  git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src123 || { echo "tp123 build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src123 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp123: syntax check failed at $C" >> $L; continue; fi
  echo "tp123: source commit $C" >> $L
  (cd $W/src123 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp123 -lze_loader >> $L 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    for b in test_dtopk:test_dtopk test_index_score_px:test_index_score_px; do
      (cd $W/src123 && nice -n 5 icpx -fsycl $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/${b%%:*}.cpp -o $W/${b##*:} >> $L 2>&1) \
        && echo "tp123: bench ${b##*:} built" >> $L || echo "tp123: bench ${b##*:} FAILED" >> $L
    done
    break
  fi
  echo "tp123: device build failed at $C (exit $rc)" >> $L
done
echo "tp123 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
