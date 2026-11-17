#!/bin/bash
# tp126 build (2026-11-16 23:2x): tp125 + kvdedup-1 and ropedev-1 on by default + idxrows-2 (shared score rows), 866df22e15 (= 6223a23c79 + the idxbc-1 bench kernel, unused by the engine); bench test_index_score_px. No benches.
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp126.log
touch $W/locks/build-tp126; trap "rm -f $W/locks/build-tp126" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
# each candidate commit: export, syntax check, device build; the first that builds wins
while [ -e $W/six.active ]; do sleep 20; done
: > $L
rc=8
for C in 866df22e15; do
  rm -rf $W/src126; mkdir -p $W/src126/tools
  git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src126 || { echo "tp126 build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src126 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp126: syntax check failed at $C" >> $L; continue; fi
  echo "tp126: source commit $C" >> $L
  (cd $W/src126 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp126 -lze_loader >> $L 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    for b in test_index_score_px:test_index_score_px; do
      (cd $W/src126 && nice -n 5 icpx -fsycl $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/${b%%:*}.cpp -o $W/${b##*:} >> $L 2>&1) \
        && echo "tp126: bench ${b##*:} built" >> $L || echo "tp126: bench ${b##*:} FAILED" >> $L
    done
    break
  fi
  echo "tp126: device build failed at $C (exit $rc)" >> $L
done
echo "tp126 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
