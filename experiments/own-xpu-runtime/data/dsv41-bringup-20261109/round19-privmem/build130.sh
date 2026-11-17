#!/bin/bash
# tp130 build (2026-11-17): 13ec276571 = 501bc070ce (tp129) + idxmem-1 (the filter's per-token buffers for 43 tokens,
# not 256: 128 -> 21 MiB per card at 1M) + allocmap-1 (OWN_ALLOC_LOG=1). Then the rux9 bench (prompt expert kernels
# with x staged once in local memory; /home/steve/dsv41-work/rux9, its README's build line) against the same source.
W=/home/steve/dsv41-work
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp130.log
touch $W/locks/build-tp130; trap "rm -f $W/locks/build-tp130" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
while [ -e $W/six.active ] || [ -e $W/HOLD_BUILDS ]; do sleep 20; done
until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ]; do sleep 20; done
: > $L
C=13ec276571
rm -rf $W/src130; mkdir -p $W/src130/tools
git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src130 || { echo "tp130 build exit 9 (source export $C)" >> $L; exit 9; }
if ! (cd $W/src130 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
  echo "tp130: syntax check failed at $C" >> $L; echo "tp130 build exit 7 in $(( $(date +%s) - t0 )) s" >> $L; exit 7; fi
echo "tp130: source commit $C" >> $L
(cd $W/src130 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp130 -lze_loader >> $L 2>&1)
rc=$?
echo "tp130 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
# rux9 bench (README "Build"), the engine's headers from src130
R=$W/rux9; rm -rf $R/isa; mkdir -p $R/isa
(cd $R && IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir="$R/isa" nice -n 5 icpx -fsycl $GPU '-options -ze-intel-enable-auto-large-GRF-mode' \
  -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 \
  -I $W/src130/src -I . bench_rux9.cpp -o bench_rux9 -lze_loader > build.log 2>&1)
rr=$?
echo "rux9 bench build exit $rr" >> $L
if [ $rr -eq 0 ]; then
  python3 -I $W/rux6/tools/sendcheck6.py $R/isa --quiet > $R/isa/sendcheck.txt 2>&1
  echo "rux9 sendcheck: $(tail -1 $R/isa/sendcheck.txt)" >> $L
  for f in $R/isa/*_simd32_entry_*.asm; do k=$(sed -n '1s#//.kernel ##p' $f); case $k in *Routed*) ;; *) continue;; esac
    s=$(grep -m1 '^//.spill size' $f | grep -o '[0-9]*$'); echo "rux9 isa: spill ${s:-0} B | sync.bar $(grep -c 'sync.bar' $f) | fence.ugm $(grep -c 'fence.ugm' $f) | ${k:0:160}"; done >> $L
fi
exit $rc
