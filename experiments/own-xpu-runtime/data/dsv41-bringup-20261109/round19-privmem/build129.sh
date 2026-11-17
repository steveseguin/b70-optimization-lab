#!/bin/bash
# tp129 build (2026-11-17 05:xx): candidates in order, the first that builds wins; the filter bench first
# tp129: 10f1b390ab = tp128 (2f159ba705) + kvdedup-2 check-sized only (cdc6e8d6e4) + OWN_IDX_DUMP (8ff2ab3400, diagnostic) + idxfilt-1 (OWN_IDX_FILT opt-in: the matrix-engine pre-filter with a proven bound, prompt halves) + test_idxfilt; fallback 8ff2ab3400 (no idxfilt)
W=/home/steve/dsv41-work
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp129.log
touch $W/locks/build-tp129; trap "rm -f $W/locks/build-tp129" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
# each candidate commit: export, syntax check, device build; the first that builds wins
while [ -e $W/six.active ]; do sleep 20; done
: > $L
rc=8
for C in 10f1b390ab 8ff2ab3400; do
  rm -rf $W/src129; mkdir -p $W/src129/tools
  git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src129 || { echo "tp129 build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src129 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp129: syntax check failed at $C" >> $L; continue; fi
  echo "tp129: source commit $C" >> $L
  if [ $C = 10f1b390ab ]; then # the filter bench first (small: its device errors show in minutes)
    if (cd $W/src129 && nice -n 5 icpx -fsycl $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_idxfilt.cpp -o $W/test_idxfilt_tp129 >> $L 2>&1); then
      echo "tp129: bench test_idxfilt_tp129 built" >> $L
    else
      echo "tp129: bench test_idxfilt FAILED" >> $L; continue
    fi
  fi
  (cd $W/src129 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp129 -lze_loader >> $L 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    break
  fi
  echo "tp129: device build failed at $C (exit $rc)" >> $L
done
echo "tp129 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
