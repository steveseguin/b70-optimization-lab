#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a40-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a40-to-a41-fullgraph.py"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a41-fullgraph.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a41-fullgraph-client.sh"
expected_base=2f72d7a9cc91b33f4c1eab91864c05381a6c5aa7ce7dd1402be0189cbf50c9f9
expected_rewriter=bad2362605ae40ad4f88da197bec2bb0dd7e6878da7e3f13e6a22361319025fc
expected_wrapper=0a3a77dc1f43ca7ed2ff3299c7b51165c68d708417489483518ddc9be636eb89
expected_client=bade97f7ec8bdc9bf969d6ffb0923882bbeb71620ea43766261a33558d7e802f
expected_source=3bbb38bc1eeb502f1605348b4447483921da3d7a0616c1474a42cfd3a07f56fc

derive() {
  Q38_A40_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor \
    --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"
}

[[ $# == 0 ]] || { printf 'FAIL: A41 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]]
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A41 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A41_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
