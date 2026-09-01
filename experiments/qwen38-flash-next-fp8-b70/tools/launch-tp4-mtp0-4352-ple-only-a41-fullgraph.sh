#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a40-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a40-to-a41-fullgraph.py"
expected_base=7f4452a9c62c9a49da68a416965280c697f9908942765e9da1a7afdcd2bd8bdb
expected_rewriter=bad2362605ae40ad4f88da197bec2bb0dd7e6878da7e3f13e6a22361319025fc
expected_derived=7848b38ba6a57be8cd9ad86e1d624b0ab1f1e0a0ecde984e54588aa7eeae4757
expected_source=fad5313c3fbe87d9c0034f3e2326c7baae45c9eedc0ab4d4a95dd78ee6a27558
libccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0
libccl_sha256=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700

derive() {
  Q38_A40_SOURCE_ONLY=1 "$base" | \
    python3 "$rewriter" launcher --derived-hash "$expected_derived"
}

[[ $# == 0 ]] || { printf 'FAIL: A41 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A41 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A41_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
for _read in 1 2 3; do
  echo "$libccl_sha256  $libccl" | sha256sum -c -
done
torch_trace=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt41/torch-trace
[[ ! -e "$torch_trace" ]] || {
  printf 'FAIL: refusing to reuse Torch trace path %s\n' "$torch_trace" >&2
  exit 1
}
export TORCH_TRACE="$torch_trace"
source <(derive)
