#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a39-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a39-to-a40-fullgraph.py"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a40-fullgraph.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a40-fullgraph-client.sh"
expected_base=28d5da00cc5331ad0793c584658846f628d9df4cfdfe8597723628465f491a51
expected_rewriter=a364ba047a24fcf985476ffc91d12f35e68c3b55836397548e330f3551446194
expected_wrapper=7f4452a9c62c9a49da68a416965280c697f9908942765e9da1a7afdcd2bd8bdb
expected_client=415d203f2752ddfccfe1963efd17cfd0483565fab592172b6c6ab5f323aa202d
expected_source=50413396e773c958b848410d5f5a0ad91c639720581140054498a60eb40b16bf

derive() {
  Q38_A39_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor \
    --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"
}

[[ $# == 0 ]] || { printf 'FAIL: A40 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]]
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A40 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A40_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
