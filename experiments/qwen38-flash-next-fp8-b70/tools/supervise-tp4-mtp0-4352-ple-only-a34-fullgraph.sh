#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a33-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a33-to-a34-fullgraph.py"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a34-fullgraph.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a34-fullgraph-client.sh"
expected_base=d2d7e09a230f616f6594b3ee56d546c39889938586a16394bc65d3fb7a27705e
expected_rewriter=3dfd9bf23e83cd63fdb8eb1d367d9c601bc55d333ba4952869ffa5c778b60a7e
expected_wrapper=6a2629debf63dc63c759d6c6eea34897ff7a0cc17b709febb1a7078499151531
expected_client=cf9b044839c5027f57bc74982328adf969c131921aba3b222704b269285da247
expected_source=863e98e122167bf1bf2882caa8711799fe425bd16eb9a7bdb94c7c11bb72aa13

derive() {
  Q38_A33_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor \
    --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"
}

[[ $# == 0 ]] || { printf 'FAIL: A34 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]]
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A34 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A34_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
