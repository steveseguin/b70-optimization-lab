#!/bin/bash
# tp118q build: tp118p + privmem-2 (blocks up to 16 tokens carry the index tables in the kernel arguments: no LensPut
# launch in guess checks / draft steps). Worktree tp118p.
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp118q.log
touch $W/locks/build-tp118q; trap "rm -f $W/locks/build-tp118q" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
# each candidate commit: export, syntax check, device build; the first that builds wins
while [ -e $W/six.active ]; do sleep 20; done
: > $L
rc=8
for C in 5dc319d3d5; do
  rm -rf $W/src118q; mkdir -p $W/src118q/tools
  git -C $W/tp118p archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src118q || { echo "tp118q build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src118q && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp118q: syntax check failed at $C" >> $L; continue; fi
  echo "tp118q: source commit $C" >> $L
  (cd $W/src118q && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp118q -lze_loader >> $L 2>&1)
  rc=$?
  [ $rc -eq 0 ] && break
  echo "tp118q: device build failed at $C (exit $rc)" >> $L
done
echo "tp118q build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
