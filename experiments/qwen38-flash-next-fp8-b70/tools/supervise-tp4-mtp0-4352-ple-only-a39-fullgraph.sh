#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a38-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a38-to-a39-fullgraph.py"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a39-fullgraph.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a39-fullgraph-client.sh"
expected_base=7fcd149ea7d9dc43b2debd1adb5bb571bdad358597e9ca175ee68651c139547e
expected_rewriter=232ef59296c75da4b27c9b7ac1779ea7d89751edacad7743f6f2c035fc4d86d6
expected_wrapper=e3f88d5d4b898e50724ad6cd83986c571fdb7293c23788a26bb29fc50a7aa6f3
expected_client=d7599824c4a31bf33e1de17e6f99312e3f7f98711f544716ed9614e99ab4dffb
expected_source=525d4a14afbd02fab0f8935592dca2a7d04eb8d51f0d8784e09890b77f806ef4

derive() {
  Q38_A38_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor \
    --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"
}

[[ $# == 0 ]] || { printf 'FAIL: A39 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]]
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A39 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A39_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
