#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a35-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a35-to-a36-fullgraph.py"
expected_base=8cea3b85a3aa332e46e35eacfdf2096e59a760343fb21d042f819442c4b8a11f
expected_rewriter=9de1393fe33bc618d2965e1f0f346f1a44565c2aefde6613ab6574822fb68d69
expected_derived=770fd21fab94a38481b2cf0c9372539e911eab6b07c38e968586655fd6f70f9b
expected_source=7101e2387c05d4d1cbb47ec691b37e51c0d2aced274f5053d5b28e5ffba89962

derive() {
  Q38_A35_SOURCE_ONLY=1 "$base" | \
    python3 "$rewriter" launcher --derived-hash "$expected_derived"
}

[[ $# == 0 ]] || { printf 'FAIL: A36 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A36 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A36_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
