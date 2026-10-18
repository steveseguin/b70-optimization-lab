#!/usr/bin/env bash
# Manual coordinator command only. No automatic retry or service restoration.
set -Eeuo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$HERE/../../../.."
nice -n 19 taskset -c 8-15,24-31 python3 -B "$HERE/verify_ready.py" </dev/null
source /tmp/claude-1000/-home-steve/fn-run/p49.env
: "${P49_LDP:?approved library path missing}"
P=experiments/own-xpu-runtime/stage2/packet124c-record-bundle
PREFIX=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
[[ ${1:-} == chain && ${2:-} == "$PWD/$P/build/device-cards01-a" ]] || exit 2
env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
 python3 -B "$HERE/chain_entry.py" queue --authorized-device-window --phase all \
 --output-root "$2" --wait-oracle \
 --prefix-windows "$PREFIX/evidence/head-k-a/window.json" "$PREFIX/evidence/head-k-b/window.json"
