#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a35-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a35-to-a36-fullgraph.py"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a36-fullgraph.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a36-fullgraph-client.sh"
expected_base=2ff5ecb94d81f884aaa9db09c7fd50600aa83592d8d820b99fc5c61c5ebf93fb
expected_rewriter=9de1393fe33bc618d2965e1f0f346f1a44565c2aefde6613ab6574822fb68d69
expected_wrapper=ce86f0f784b505d7ce123cc4f38a7ccb0cb812cc17387ed87ceb8f0fd6145286
expected_client=1949bbc71a62847525156d05f73851a3c9b4dab058bc7b4931e2a3dba8604b5f
expected_source=976a9500e77a968abf95bb6263bc9b056e9d0af65dcb4deb7a7500995770579c

derive() {
  Q38_A35_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor \
    --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"
}

[[ $# == 0 ]] || { printf 'FAIL: A36 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]]
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A36 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A36_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
