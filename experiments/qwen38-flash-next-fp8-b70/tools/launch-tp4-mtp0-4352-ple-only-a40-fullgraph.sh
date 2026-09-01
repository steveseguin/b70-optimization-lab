#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a39-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a39-to-a40-fullgraph.py"
expected_base=e3f88d5d4b898e50724ad6cd83986c571fdb7293c23788a26bb29fc50a7aa6f3
expected_rewriter=a364ba047a24fcf985476ffc91d12f35e68c3b55836397548e330f3551446194
expected_derived=3b8c3833177b586a478945ef63851443e8971eb5858cac327ca5258b178b14e1
expected_source=065a3579f9c24193cd80b2c899f298e4925fd894c608665396cdac6db7804b29
libccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0
libccl_sha256=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700

derive() {
  Q38_A39_SOURCE_ONLY=1 "$base" | \
    python3 "$rewriter" launcher --derived-hash "$expected_derived"
}

[[ $# == 0 ]] || { printf 'FAIL: A40 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A40 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A40_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
for _read in 1 2 3; do
  echo "$libccl_sha256  $libccl" | sha256sum -c -
done
torch_trace=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt40/torch-trace
[[ ! -e "$torch_trace" ]] || {
  printf 'FAIL: refusing to reuse Torch trace path %s\n' "$torch_trace" >&2
  exit 1
}
export TORCH_TRACE="$torch_trace"
source <(derive)
