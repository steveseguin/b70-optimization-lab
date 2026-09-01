#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a38-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a38-to-a39-fullgraph.py"
expected_base=c4cf7f8e9a5edfd52f6624668503899ca0b60f52acc4ea93f4d153900f0a3915
expected_rewriter=232ef59296c75da4b27c9b7ac1779ea7d89751edacad7743f6f2c035fc4d86d6
expected_derived=761fad8e8f7d7c2977178b21053a5013f293e282656eb6cdf22365c3f8b195cd
expected_source=426edee7f7a307a389f8d2d6be283bbf7fe9216917949b45c52edc4d0e79186a
libccl=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0
libccl_sha256=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700

derive() {
  Q38_A38_SOURCE_ONLY=1 "$base" | \
    python3 "$rewriter" launcher --derived-hash "$expected_derived"
}

[[ $# == 0 ]] || { printf 'FAIL: A39 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A39 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A39_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
for _read in 1 2 3; do
  echo "$libccl_sha256  $libccl" | sha256sum -c -
done
torch_trace=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-4352-ple-only-r1-attempt39/torch-trace
[[ ! -e "$torch_trace" ]] || {
  printf 'FAIL: refusing to reuse Torch trace path %s\n' "$torch_trace" >&2
  exit 1
}
export TORCH_TRACE="$torch_trace"
source <(derive)
