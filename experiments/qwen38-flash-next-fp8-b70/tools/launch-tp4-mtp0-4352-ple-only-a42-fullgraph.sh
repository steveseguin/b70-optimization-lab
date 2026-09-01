#!/usr/bin/env bash
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a41-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a41-to-a42-fullgraph.py"
expected_base=0a3a77dc1f43ca7ed2ff3299c7b51165c68d708417489483518ddc9be636eb89
expected_rewriter=df0383af4778ed7294092afc9cc951979dd3b9c62528b4d591fe346da28b8bed
expected_derived=b9ee60b7cf602eb207c7036eadf879e98e311e52d3d67cf77492559ed96065aa
expected_source=5cebc6a2a6c6b4d04dafaad209faa41c505f0c94ff7b8cfdf532f42ca51d378b
libccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0
libccl_sha256=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700
derive() { Q38_A41_SOURCE_ONLY=1 "$base" | python3 "$rewriter" launcher --derived-hash "$expected_derived"; }
[[ $# == 0 ]] || { printf 'FAIL: A42 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A42 launcher source drift\n' >&2; exit 1; }
if [[ "${Q38_A42_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
for _read in 1 2 3; do
  echo "$libccl_sha256  $libccl" | sha256sum -c -
done
torch_trace=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt42/torch-trace
[[ ! -e "$torch_trace" ]] || { printf 'FAIL: refusing to reuse Torch trace path %s\n' "$torch_trace" >&2; exit 1; }
export TORCH_TRACE="$torch_trace"
source <(derive)
