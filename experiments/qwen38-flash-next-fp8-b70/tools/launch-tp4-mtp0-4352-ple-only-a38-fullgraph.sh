#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a37-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a37-to-a38-fullgraph.py"
expected_base=4770b437848c5ed913d9ce74055b91dab0e7eaa3845e9b9ac42ea2777bc508a7
expected_rewriter=1bf85dd7198d709e1925671dbaa507c330ce5f353e748a32cb4c3784bf1959a1
expected_derived=74413cb6784f47328b923fefd2a7fc523d943140eba2a5fca8161372e86c2c31
expected_source=ff3331515a55096ed76085ddb98ab36f33582b4b59822225b053d55a91d7e63b

derive() {
  Q38_A37_SOURCE_ONLY=1 "$base" | \
    python3 "$rewriter" launcher --derived-hash "$expected_derived"
}

[[ $# == 0 ]] || { printf 'FAIL: A38 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A38 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A38_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
torch_trace=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt38/torch-trace
[[ ! -e "$torch_trace" ]] || {
  printf 'FAIL: refusing to reuse Torch trace path %s\n' "$torch_trace" >&2
  exit 1
}
export TORCH_TRACE="$torch_trace"
source <(derive)
