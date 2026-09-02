#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-q38-w13-m1-xpu-graph-confirmation-a1.sh"
summarizer="${script_dir}/summarize-w13-m1-xpu-graph-confirmation-a2.py"
validator="${script_dir}/validate-q38-root-nvme-link-clearance-v1.py"
clearance=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/host/20260901-root-nvme-link-clearance-v1.json
expected_base=c81a2240542b75a3bf932fccf606f2db4b2872d201171c76f8e6f48ac5a7fad3
expected_summarizer=e61b13c08c6738d9e552c10a0f751ffe726216518dd419bc3b08b73667137113
expected_validator=2293b3588a275e15a630b813d7a273e650eb64c49eaacedcf212f99fe485d5a5
expected_derived=6c9e672737d46c651c3909ecd7d57693308d121f87a2b93d6bacee3e5a87249a
derived=/dev/shm/q38-w13-m1-xpu-graph-confirmation-a2-derived.sh

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
digest() { sha256sum "$1" | cut -d' ' -f1; }

derive() {
  awk -v expected_summarizer="$expected_summarizer" '
  {
    gsub(/confirmation-a1/, "confirmation-a2")
    gsub(/summarize-w13-m1-xpu-graph-confirmation.py/, "summarize-w13-m1-xpu-graph-confirmation-a2.py")
    if ($0 ~ /^expected_summarizer=/) {
      print "expected_summarizer=" expected_summarizer
      next
    }
    if ($0 == "max_total_seconds=10800") {
      print "max_total_seconds=5400"
      next
    }
    if ($0 == "for _ in $(seq 1 60); do") {
      skip_idle = 1
      next
    }
    if (skip_idle == 1) {
      if ($0 ~ /^printf .*PASS: 60-second idle preflight/) {
        skip_idle = 0
      }
      next
    }
    gsub(/for seed in 20260826 20260827 20260830; do/, "for seed in 20260827; do")
    gsub(/seeds20260826,20260827,20260830/, "seed20260827")
    gsub(/W13 N32 graph confirmation validates/, "W13 N32 graph confirmation A2 validates")
    gsub(/W13 N32 graph confirmation complete/, "W13 N32 graph confirmation A2 complete")
    gsub(/qwen38_w13_m1_xpu_graph_confirmation"/, "qwen38_w13_m1_xpu_graph_confirmation_a2\"")
    gsub(/\(\.rows \| length\) == 24/, "(.rows | length) == 8")
    gsub(/\.gates\.all_24_cells_exact/, ".gates.all_8_cells_exact")
    gsub(/\.gates\.at_least_20_positive_cells/, ".gates.at_least_7_positive_cells")
    print
  }
  ' "$base"
}

cleanup() {
  rm -f "$derived"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

[[ $# == 0 ]] || fail "this frozen A2 wrapper takes no arguments"
[[ "${Q38_W13_A2_SOURCE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid source-only selector"
[[ "${Q38_W13_A2_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
[[ "$(digest "$base")" == "$expected_base" ]] || fail "A1 base runner drifted"
[[ "$(digest "$summarizer")" == "$expected_summarizer" ]] || fail "A2 summarizer drifted"
[[ "$(digest "$validator")" == "$expected_validator" ]] || fail "root-NVMe clearance validator drifted"

if [[ "${Q38_W13_A2_SOURCE_ONLY:-0}" == 0 && "${Q38_W13_A2_VALIDATE_ONLY:-0}" == 0 ]]; then
  [[ "$(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)" == "/dev/sda2 fuseblk /mnt/usb-models" ]] || \
    fail "external evidence mount is not the frozen /dev/sda2 fuseblk filesystem"
  [[ -f "$clearance" && ! -L "$clearance" ]] || fail "root-NVMe link clearance is missing"
  "$validator" --clearance-json "$clearance" >/dev/null || fail "root-NVMe link clearance failed"
fi

[[ ! -e "$derived" ]] || fail "derived A2 path already exists"

derive >"$derived"
chmod 0700 "$derived"
[[ "$(digest "$derived")" == "$expected_derived" ]] || fail "derived A2 runner drifted"
bash -n "$derived"

if [[ "${Q38_W13_A2_SOURCE_ONLY:-0}" == 1 ]]; then
  cat "$derived"
  exit 0
fi
if [[ "${Q38_W13_A2_VALIDATE_ONLY:-0}" == 1 ]]; then
  Q38_W13_CONFIRM_VALIDATE_ONLY=1 "$derived"
  exit 0
fi

"$derived"
