#!/bin/bash
# tp128 build (2026-11-17 03:xx): candidates in order, the first that builds wins
# tp128 (2026-11-17): 0e4e3353ee = tp127 (85d7bb0a8c) + dtopk-2 on by default (2025c86a51, the fallback) + dtopk-2 batched launches (OWN_IDX_DTOPK_MB, opt-in); e7848e2564 adds idxbc-2 (OWN_IDX_CK_R, opt-in) and the bench with BENCH_M / BENCH_LENS; 2f159ba705 adds kvdedup-2 (OWN_KV_DEDUP_CK, opt-in)
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp128.log
touch $W/locks/build-tp128; trap "rm -f $W/locks/build-tp128" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
# each candidate commit: export, syntax check, device build; the first that builds wins
while [ -e $W/six.active ]; do sleep 20; done
: > $L
rc=8
for C in 2f159ba705 e7848e2564 0e4e3353ee 2025c86a51; do
  rm -rf $W/src128; mkdir -p $W/src128/tools
  git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src128 || { echo "tp128 build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src128 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp128: syntax check failed at $C" >> $L; continue; fi
  echo "tp128: source commit $C" >> $L
  (cd $W/src128 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp128 -lze_loader >> $L 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    for b in test_index_score_px:test_index_score_px_tp128; do
      (cd $W/src128 && nice -n 5 icpx -fsycl $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/${b%%:*}.cpp -o $W/${b##*:} >> $L 2>&1) \
        && echo "tp128: bench ${b##*:} built" >> $L || echo "tp128: bench ${b##*:} FAILED" >> $L
    done
    break
  fi
  echo "tp128: device build failed at $C (exit $rc)" >> $L
done
echo "tp128 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
