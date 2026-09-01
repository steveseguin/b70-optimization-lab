#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a36-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a36-to-a37-fullgraph.py"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a37-fullgraph.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a37-fullgraph-client.sh"
expected_base=5d9a2a142aad06b81081ccae4bb63f5676c2fa0e8aca879fd0d7eef78b2aad3a
expected_rewriter=8ce5637d024992d9d3836f7cb6bb322c667e24e6fed09fdabc43024c52307fd3
expected_wrapper=4770b437848c5ed913d9ce74055b91dab0e7eaa3845e9b9ac42ea2777bc508a7
expected_client=eb1e81820de1766b8e577dd3296bb800dcbfd7ca60d7e75f33e8ee3dda15bd1c
expected_source=8415f9d53f7b24d80df671bea53c9a605b11c96d046fb2b88c11c3c0d84168b8

derive() {
  Q38_A36_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor \
    --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"
}

[[ $# == 0 ]] || { printf 'FAIL: A37 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]]
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A37 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A37_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
