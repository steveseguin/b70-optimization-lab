#!/bin/bash
# tp131 build (2026-11-17): a00da671bf = fd8d238cd4 (ifldiag-1: OWN_IFL_DIAG) + the extra rux9 forms behind
# -DOWN_RUX9_TY (added to the build flags only when bench_rux9_f7 compiles); 45387d19dc = 029e51952b + rux9-2 (OWN_RUX9_TY: IQ2_XXS / IQ1_S gate + up on RoutedS9 too;
# only if the rux9 bench builds with -DRUX4_FMT=7 first: bench_rux9_f7); 029e51952b = b956f44c23 + idxfilt-4 (OWN_IDX_FILT_BC: the candidate index layers 24-36 by
# the pre-filter); b956f44c23 = 688f7bbcb2 + idxfilt-3 (OWN_IDX_FILT_SEL: the filtered layers' selects over the
# survivors only); 688f7bbcb2 = 13ec276571 (tp130) + rux9-1 (OWN_RUX9=1..4: prompt IQ2_S gate + up on RoutedS9). The
# filter bench (with TopKSelF's comparison) first; candidates in order, the first that builds wins.
W=/home/steve/dsv41-work
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
L=$W/build-tp131.log
touch $W/locks/build-tp131; trap "rm -f $W/locks/build-tp131" EXIT  # six-card gates wait while a build runs
t0=$(date +%s)
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
while [ -e $W/six.active ] || [ -e $W/HOLD_BUILDS ]; do sleep 20; done
until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ]; do sleep 20; done
: > $L
rc=8
# the rux9 bench with IQ2_XXS / IQ1_S gate + up (README: -DRUX4_FMT=7), against tp130's sources (the same kernels)
R=$W/rux9; CL="a00da671bf 029e51952b b956f44c23 688f7bbcb2"
# (rux9 closed by c130's bench: bitwise but -0.2..-1.2 % only; the IQ2_XXS / IQ1_S bench is not built)
if false && [ -d $W/src130/src ]; then
  rm -rf $R/isa7; mkdir -p $R/isa7
  if (cd $R && IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir="$R/isa7" nice -n 5 icpx -fsycl $GPU '-options -ze-intel-enable-auto-large-GRF-mode' \
      -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -DRUX4_FMT=7 \
      -I $W/src130/src -I . bench_rux9.cpp -o bench_rux9_f7 -lze_loader > build7.log 2>&1); then
    python3 -I $W/rux6/tools/sendcheck6.py $R/isa7 --quiet > $R/isa7/sendcheck.txt 2>&1
    echo "rux9 f7 bench build exit 0; sendcheck: $(tail -1 $R/isa7/sendcheck.txt)" >> $L
    F="$F -DOWN_RUX9_TY=1"
  else echo "rux9 f7 bench build FAILED (rux9-2 left out)" >> $L; fi
fi
for C in $CL; do
  rm -rf $W/src131; mkdir -p $W/src131/tools
  git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src131 || { echo "tp131 build exit 9 (source export $C)" >> $L; exit 9; }
  if ! (cd $W/src131 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp >> $L 2>&1); then
    echo "tp131: syntax check failed at $C" >> $L; continue; fi
  if [ $C = a00da671bf ] || [ $C = 029e51952b ] || [ $C = b956f44c23 ]; then # the filter bench (TopKSelF, idxfilt-4) first: small, its errors show in minutes
    if (cd $W/src131 && nice -n 5 icpx -fsycl $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_idxfilt.cpp -o $W/test_idxfilt_tp131 >> $L 2>&1); then
      echo "tp131: bench test_idxfilt_tp131 built" >> $L
    else
      echo "tp131: bench test_idxfilt FAILED at $C" >> $L; continue
    fi
  fi
  echo "tp131: source commit $C (flags: $(echo $F | grep -o 'OWN_RUX9_TY=1' || echo 'no OWN_RUX9_TY'))" >> $L
  (cd $W/src131 && nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp131 -lze_loader >> $L 2>&1)
  rc=$?
  [ $rc -eq 0 ] && break
  echo "tp131: device build failed at $C (exit $rc)" >> $L
done
echo "tp131 build exit $rc in $(( $(date +%s) - t0 )) s" >> $L
# densews: the four-row dense-row forms bench (densews/bench_r4.cpp, PART_PICK) against tp131's sources, ISA dumped
if [ -d $W/src131/src ]; then
  DW=$W/densews; rm -rf $DW/isa; mkdir -p $DW/isa
  (cd $DW && IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir="$DW/isa" nice -n 5 icpx -fsycl $GPU '-options -ze-intel-enable-auto-large-GRF-mode' \
    -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -DPART_PICK -I $W/src131/src bench_r4.cpp \
    -o bin/bench_r4 > logs/build-r4.log 2>&1)
  rd=$?
  echo "densews bench build exit $rd" >> $L
  if [ $rd -eq 0 ]; then
    for f in $DW/isa/*_simd32_entry_*.asm; do k=$(sed -n '1s#//.kernel ##p' $f); case $k in *DenseRowsWS*) ;; *) continue;; esac
      s=$(grep -m1 '^//.spill size' $f | grep -o '[0-9]*$'); p=$(grep -m1 -i 'private' $f | grep -o '[0-9]*$' | head -1)
      echo "densews isa: spill ${s:-0} B | numGRF $(grep -m1 -o 'numGRF=[0-9]*' $f | cut -d= -f2) | ${k:0:150}"; done >> $L
  fi
fi
exit $rc
