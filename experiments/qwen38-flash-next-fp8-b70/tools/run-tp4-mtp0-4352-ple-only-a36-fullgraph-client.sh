#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a35-fullgraph-client.sh"
rewriter="${script_dir}/rewrite-q38-a35-to-a36-fullgraph.py"
runtime_verifier="${script_dir}/verify-q38-a36-fullgraph-runtime.py"
expected_base=264c27d0fb014f6a7340f392b70df84e7250f04a71f91eab2570965ba4c10bf5
expected_rewriter=9de1393fe33bc618d2965e1f0f346f1a44565c2aefde6613ab6574822fb68d69
expected_runtime_verifier=256de72996103f284635c7402ceaa3d41ac8af877aabe773a1af10a84f09ae16
expected_source=603faab8913d831dc7215a30f2b5baa0415d4f6ca15b6da7b88ab74b8a08e449

derive() {
  Q38_A35_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client \
    --runtime-verifier-hash "$expected_runtime_verifier"
}

[[ $# == 0 ]] || { printf 'FAIL: A36 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$runtime_verifier" | cut -d' ' -f1)" == "$expected_runtime_verifier" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A36 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A36_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
