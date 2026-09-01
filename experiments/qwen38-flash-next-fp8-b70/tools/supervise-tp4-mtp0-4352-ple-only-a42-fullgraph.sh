#!/usr/bin/env bash
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a41-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a41-to-a42-fullgraph.py"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a42-fullgraph.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a42-fullgraph-client.sh"
expected_base=533b73ce9ad2493aa4f409c8dbd908830bf304c292444eac5f8915946a739b2c
expected_rewriter=df0383af4778ed7294092afc9cc951979dd3b9c62528b4d591fe346da28b8bed
expected_wrapper=62f584a1dccb04f5135208b875a1c1813362f4307b3b007b629f3be7a19f340d
expected_client=0d179506dfa6a9c8f66106932b327cfc12bf3f2d0af7267a9429acd626fc72ad
expected_source=285d0367048e251ddcb45a85a1daf4079642ae4645445f573a0de1d4e7d3b219
derive() { Q38_A41_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"; }
[[ $# == 0 ]] || { printf 'FAIL: A42 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]]
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A42 supervisor source drift\n' >&2; exit 1; }
if [[ "${Q38_A42_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
