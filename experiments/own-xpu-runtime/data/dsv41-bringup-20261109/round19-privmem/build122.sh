#!/bin/bash
# tp122 build (2026-11-16): tp121 (dtopk-1, the distributed index select) + tp120's eng-warm-1 / eng-spread-1 /
# hostmem-1, built with ocloc -exclude_ir (no SPIR-V in the kernel images: the runtime keeps one SPIR-V copy per
# context, ~1.3 GiB of host RAM; hostmem/FINDINGS.md). Bench: test_dtopk. Check the kernels' code against tp120's
# with hostmem/zebin_sizes.py.
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp122.log
touch $W/locks/build-tp122; trap "rm -f $W/locks/build-tp122" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
# each candidate commit: export, syntax check, device build; the first that builds wins
while [ -e $W/six.active ]; do sleep 20; done
: > $L
rc=8
for C in 9bc805e72a; do
  rm -rf $W/src122; mkdir -p $W/src122/tools
  git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src122 || { echo "tp122 build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src122 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp122: syntax check failed at $C" >> $L; continue; fi
  echo "tp122: source commit $C" >> $L
  (cd $W/src122 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp122 -lze_loader >> $L 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    for b in test_dtopk:test_dtopk; do
      (cd $W/src122 && nice -n 5 icpx -fsycl $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/${b%%:*}.cpp -o $W/${b##*:} >> $L 2>&1) \
        && echo "tp122: bench ${b##*:} built" >> $L || echo "tp122: bench ${b##*:} FAILED" >> $L
    done
    break
  fi
  echo "tp122: device build failed at $C (exit $rc)" >> $L
done
echo "tp122 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
