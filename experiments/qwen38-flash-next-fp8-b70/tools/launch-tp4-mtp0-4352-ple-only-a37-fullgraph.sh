#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a36-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a36-to-a37-fullgraph.py"
expected_base=ce86f0f784b505d7ce123cc4f38a7ccb0cb812cc17387ed87ceb8f0fd6145286
expected_rewriter=8ce5637d024992d9d3836f7cb6bb322c667e24e6fed09fdabc43024c52307fd3
expected_derived=eb3d3995be5a4bd433f95733124e63d1a57e24a83a35461a33e9ce667f280014
expected_source=f1e7424b4c3e453c0118dd8d56b1c71afed71dcb062975e3f6f7cd120cd5e85e

derive() {
  Q38_A36_SOURCE_ONLY=1 "$base" | \
    python3 "$rewriter" launcher --derived-hash "$expected_derived"
}

[[ $# == 0 ]] || { printf 'FAIL: A37 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A37 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A37_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
torch_trace=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt37/torch-trace
[[ ! -e "$torch_trace" ]] || {
  printf 'FAIL: refusing to reuse Torch trace path %s\n' "$torch_trace" >&2
  exit 1
}
export TORCH_TRACE="$torch_trace"
source <(derive)
