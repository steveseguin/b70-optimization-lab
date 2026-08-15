#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
stamp=${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}
root=${VALIDATION_ROOT:-/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/independent-validation-$stamp}

if [[ -e "$root" ]]; then
  printf 'refusing existing validation root: %s\n' "$root" >&2
  exit 2
fi
mkdir -p -- "$root"
printf 'stamp=%s\nroot=%s\n' "$stamp" "$root" > "$root/matrix.env"

run_arm() {
  local mode=$1 pair=$2 name=$3 port=$4 baseline=${5:-}
  local arm_root="$root/$name"
  printf 'starting %s mode=%s pair=%s\n' "$name" "$mode" "$pair" | tee -a "$root/progress.log"
  set +e
  PORT="$port" STAMP="$stamp-$name" LABEL="$name" \
    "$here/run-arm.sh" "$mode" "$pair" "$arm_root" "$baseline"
  local rc=$?
  set -e
  printf '%s\t%s\n' "$name" "$rc" >> "$root/arm-exit-codes.tsv"
  if [[ ! -s "$arm_root/data/bench.json" ]]; then
    printf 'arm %s produced no benchmark; aborting matrix\n' "$name" >&2
    exit 5
  fi
}

run_arm nospec 0,1 nospec-01a 19622
run_arm spec   0,1 spec-01a   19622 "$root/nospec-01a/data/quality.json"
run_arm nospec 2,3 nospec-23a 19623 "$root/nospec-01a/data/quality.json"
run_arm spec   2,3 spec-23a   19623 "$root/nospec-23a/data/quality.json"
run_arm spec   0,1 spec-01b   19622 "$root/nospec-01a/data/quality.json"
run_arm spec   2,3 spec-23b   19623 "$root/nospec-23a/data/quality.json"

"$here/analyze.py" "$root" --out "$root/analysis.json" --markdown "$root/analysis.md"
find "$root" -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
  > "$root/SHA256SUMS"
printf 'validation complete: %s\n' "$root"

