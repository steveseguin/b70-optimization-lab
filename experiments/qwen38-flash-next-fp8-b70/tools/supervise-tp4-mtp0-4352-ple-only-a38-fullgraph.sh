#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a37-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a37-to-a38-fullgraph.py"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a38-fullgraph.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a38-fullgraph-client.sh"
expected_base=2d7e0f2ec72c016f8fd79d4e75505fe87bcb0a8ccb1aea6a0ba266d03fcf75ec
expected_rewriter=1bf85dd7198d709e1925671dbaa507c330ce5f353e748a32cb4c3784bf1959a1
expected_wrapper=c4cf7f8e9a5edfd52f6624668503899ca0b60f52acc4ea93f4d153900f0a3915
expected_client=33a43865033539c699f73ecabdfee41a9bb2ea17e5ad4ffdc0088678d02c5a81
expected_source=c5a145f7b1b46010e7a72c5e668deff389be0e0420566ea5507c5f7685a970e4

derive() {
  Q38_A37_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor \
    --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"
}

[[ $# == 0 ]] || { printf 'FAIL: A38 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]]
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A38 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A38_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
