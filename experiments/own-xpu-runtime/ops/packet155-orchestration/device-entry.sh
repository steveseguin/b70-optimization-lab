#!/usr/bin/env bash
# Manual coordinator command only. No automatic retry or service restoration.
set -Eeuo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$HERE/../../../.."
nice -n 19 taskset -c 8-15,24-31 python3 -B "$HERE/verify_ready.py" </dev/null
P=experiments/own-xpu-runtime/stage2/packet155-record-bundle9
PREFIX=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
[[ ${1:-} == chain && ${2:-} == "$PWD/$P/build/device-cards01-p155-a" ]] || exit 2
env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH=/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib \
 python3 -B "$HERE/chain_entry.py" queue --authorized-device-window --phase all \
 --output-root "$2" --wait-oracle \
 --prefix-windows "$PREFIX/evidence/head-k-a/window.json" "$PREFIX/evidence/head-k-b/window.json"
