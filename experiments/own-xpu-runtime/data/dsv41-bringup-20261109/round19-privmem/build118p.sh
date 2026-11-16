#!/bin/bash
# tp118p build (tp118 + privmem-1: the index kernels' per-token tables in card memory, ~0.94 GiB per card of driver private
# buffers gone; + tpd-2: engram time split in the reports). Worktree tp118p.
W=/home/steve/dsv41-work; E=$W/tp114src/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp118p.log
touch $W/locks/build-tp118p; trap "rm -f $W/locks/build-tp118p" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
# each candidate commit: export, syntax check, device build; the first that builds wins
while [ -e $W/six.active ]; do sleep 20; done
: > $L
rc=8
for C in 5d6c2ae46a; do
  rm -rf $W/src118p; mkdir -p $W/src118p/tools
  git -C $W/tp118p archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src118p || { echo "tp118p build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src118p && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp118p: syntax check failed at $C" >> $L; continue; fi
  echo "tp118p: source commit $C" >> $L
  (cd $W/src118p && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp118p -lze_loader >> $L 2>&1)
  rc=$?
  [ $rc -eq 0 ] && break
  echo "tp118p: device build failed at $C (exit $rc)" >> $L
done
echo "tp118p build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
