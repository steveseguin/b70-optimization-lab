#!/usr/bin/env bash
# Called only by the units constructed by orchestrate.py, never by CPU tests.
set -Eeuo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
LOG=$HERE/orchestrate.log
trap 'rc=$?; printf "%s device-entry EXIT role=%s rc=%s\n" "$(date -u +%FT%TZ)" "${1:-unset}" "$rc" >> "$LOG"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
cd "$HERE/../../../.."
source /tmp/claude-1000/-home-steve/fn-run/p49.env
: "${P49_LDP:?approved library path missing}"
P=experiments/own-xpu-runtime/stage2/packet64-record-bundle
PREFIX=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
OUT=/home/steve/own-xpu-runtime-results/packet64-record-bundle/build/device-cards01-a
case "${1:-}" in
  chain)
    # Exact WINDOW.md chain invocation, under its declared closed environment.
    env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
      bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle \
      --prefix-windows "$PREFIX/evidence/head-k-a/window.json" "$PREFIX/evidence/head-k-b/window.json"
    ;;
  companion)
    case "${2:-}" in
      1-split23-production-control) PLACEMENT=1-split23 ;;
      1-production-control) PLACEMENT=1 ;;
      *) echo 'REFUSED: unknown companion selection' >&2; exit 2 ;;
    esac
    V=experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes
    # This entry owns one lease, including hold checks, teardown and postflight.
    # Never acquire lane-B.lock here: double reservation would deadlock/refuse.
    env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
      python3 -B "$V/screen.py" --profile tp2 --lane B --placement "$PLACEMENT" \
      --lineage "$P/selections/$2" --seal "$P/selections/$2/screen-seal.json" \
      --authorized-device-window --fault-review "$3" --output "$4"
    ;;
  *) echo 'REFUSED: expected chain or companion' >&2; exit 2 ;;
esac
