#!/usr/bin/env bash
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a41-fullgraph-client.sh"
rewriter="${script_dir}/rewrite-q38-a41-to-a42-fullgraph.py"
expected_base=bade97f7ec8bdc9bf969d6ffb0923882bbeb71620ea43766261a33558d7e802f
expected_rewriter=df0383af4778ed7294092afc9cc951979dd3b9c62528b4d591fe346da28b8bed
expected_source=e4b4d4afed55ee2c9fe869a855d47b9574ed2e7f0ec7aeb88d1563043c36f96a
derive() { Q38_A41_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client; }
[[ $# == 0 ]] || { printf 'FAIL: A42 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A42 client source drift\n' >&2; exit 1; }
if [[ "${Q38_A42_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
