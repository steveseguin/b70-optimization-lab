#!/usr/bin/env bash
# Coordinator manual entry only; orchestrate.py never executes this file.
set -Eeuo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
LOG=$HERE/orchestrate.log
trap 'rc=$?; printf "%s device-entry EXIT role=%s rc=%s\n" "$(date -u +%FT%TZ)" "${1:-unset}" "$rc" >> "$LOG"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
cd "$HERE/../../../.."
nice -n 19 taskset -c 8-15,24-31 python3 -B "$HERE/verify_ready.py" </dev/null
source /tmp/claude-1000/-home-steve/fn-run/p49.env
: "${P49_LDP:?approved library path missing}"
P=experiments/own-xpu-runtime/stage2/packet84-record-bundle
PREFIX=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
OUT=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet84-record-bundle/build/device-cards01-a
case "${1:-}" in
  chain)
    # Exact WINDOW.md chain invocation, under its declared closed environment.
    env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
      bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle \
      --prefix-windows "$PREFIX/evidence/head-k-a/window.json" "$PREFIX/evidence/head-k-b/window.json"
    ;;
  *) echo 'REFUSED: expected chain' >&2; exit 2 ;;
esac
