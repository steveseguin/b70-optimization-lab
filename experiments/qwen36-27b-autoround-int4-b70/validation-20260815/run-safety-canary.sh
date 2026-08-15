#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../../.." && pwd)
stamp=${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}
root=${VALIDATION_ROOT:-/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/upstream-safety-canary-$stamp}
suite="$here/safety-canary-suite.json"
cache_root=${VALIDATION_VLLM_CACHE_ROOT:-/mnt/usb-models/llm-runtime/vllm-cache/qwen27-partition-safety-6aed46a}

if [[ -e "$root" ]]; then
  printf 'refusing existing validation root: %s\n' "$root" >&2
  exit 2
fi
mkdir -p -- "$root"
printf 'stamp=%s\nroot=%s\nlab_head=%s\nkernel_head=%s\nxpu_extension_sha256=%s\ngdn_device_library_sha256=%s\nsuite_sha256=%s\n' \
  "$stamp" "$root" "$(git -C "$repo" rev-parse HEAD)" \
  "$(git -C /home/steve/src/vllm-xpu-kernels rev-parse HEAD)" \
  "$(sha256sum /home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so | awk '{print $1}')" \
  "$(sha256sum /home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so | awk '{print $1}')" \
  "$(sha256sum "$suite" | awk '{print $1}')" > "$root/matrix.env"

run_arm() {
  local mode=$1 name=$2 baseline=${3:-}
  printf 'starting %s mode=%s pair=0,1\n' "$name" "$mode" \
    | tee -a "$root/progress.log"
  set +e
  VALIDATION_SUITE_OVERRIDE="$suite" \
  VALIDATION_RUN_QUALITY=0 \
  VALIDATION_BENCH_MAX_TOKENS=512 \
  VALIDATION_VLLM_CACHE_ROOT="$cache_root" \
  PORT=19622 STAMP="$stamp-$name" LABEL="$name" \
    "$here/run-arm.sh" "$mode" 0,1 "$root/$name" "$baseline"
  local rc=$?
  set -e
  printf '%s\t%s\n' "$name" "$rc" >> "$root/arm-exit-codes.tsv"
  return "$rc"
}

finalize() {
  find "$root" -type f ! -name SHA256SUMS -print0 | sort -z \
    | xargs -0 sha256sum > "$root/SHA256SUMS"
}
trap finalize EXIT

run_arm nospec-latest target-01a
run_arm spec-native-partition spec-01a

set +e
"$here/analyze-safety-canary.py" "$root" --out "$root/analysis.json" \
  > "$root/analysis.stdout.log"
first_rc=$?
set -e
if [[ "$first_rc" != 0 ]]; then
  printf 'first target/spec pair failed strict parity; stopping before repeats\n' \
    | tee -a "$root/progress.log" >&2
  exit "$first_rc"
fi

run_arm nospec-latest target-01b
run_arm spec-native-partition spec-01b
"$here/analyze-safety-canary.py" "$root" --out "$root/analysis.json" \
  > "$root/analysis.stdout.log"
printf 'focused safety canary passed: %s\n' "$root"
