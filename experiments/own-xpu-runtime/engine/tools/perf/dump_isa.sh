#!/bin/bash
# Ahead-of-time compile one bench-size translation unit for the B70 (intel_gpu_bmg_g31) with IGC's shader dumps on,
# so the kernels' machine code (.asm) lands in a directory. IGC runs on the host during the AOT step: no GPU is
# touched (nothing is executed; the output binary is not run).
#   dump_isa.sh OUT_DIR SOURCE.cpp [extra icpx args...]
#   e.g. dump_isa.sh /home/steve/dsv41-work/perf/isa-norm_ff engine/tools/bench/bench_norm_ff.cpp
# Rules (host has 15 GiB): one compile at a time (flock), nice -n 10, refuses below 6 GiB MemAvailable.
# SRC_ROOT=DIR compiles against another kernel source tree (e.g. /home/steve/dsv41-work/src82/src, the profiled
# build's snapshot) instead of engine/src.
# Never point this at own_run_v41.cpp (the engine main); use a small TU that instantiates the kernels instead.
set -uo pipefail
OUT=$(realpath -m "$1"); SRC=$(realpath "$2"); shift 2
case "$SRC" in *own_run_v41*) echo "refusing to compile the engine main" >&2; exit 2;; esac
ENG=$(cd "$(dirname "$0")/../.." && pwd)            # engine/
avail_kb=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
if (( avail_kb < 6 * 1024 * 1024 )); then echo "MemAvailable $((avail_kb / 1024)) MiB < 6 GiB: not compiling" >&2; exit 3; fi
mkdir -p "$OUT"
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
P=/opt/intel/oneapi/pti/latest
exec 9>/tmp/dsv41-perf-dump.lock
flock 9
t0=$(date +%s)
cd "$ENG"
IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir="$OUT" nice -n 10 icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 \
    -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 \
    -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I "${SRC_ROOT:-src}" -I tools/bench -I "$P/include" \
    "$SRC" -o "$OUT/a.out" -L "$P/lib" -lpti_view "$@" > "$OUT/build.log" 2>&1
rc=$?
rm -f "$OUT/a.out"
echo "exit $rc in $(( $(date +%s) - t0 )) s" >> "$OUT/build.log"
# keep only what the census needs (the .ll / .visa dumps are large)
# (KEEP_VISA=1 keeps the vISA text: with -gline-tables-only it carries the source lines, see isa_census.py --lines)
rm -f "$OUT"/*.ll "$OUT"/*.isaasm "$OUT"/*.progbin "$OUT"/*.spv 2>/dev/null || true
[ "${KEEP_VISA:-0}" = 1 ] || rm -f "$OUT"/*.visaasm 2>/dev/null || true
echo "$OUT: $(ls "$OUT"/*.asm 2>/dev/null | wc -l) kernels, exit $rc"
