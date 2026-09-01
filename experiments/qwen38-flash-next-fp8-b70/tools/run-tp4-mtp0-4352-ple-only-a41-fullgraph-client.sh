#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a40-fullgraph-client.sh"
rewriter="${script_dir}/rewrite-q38-a40-to-a41-fullgraph.py"
runtime_verifier="${script_dir}/verify-q38-a37-fullgraph-runtime.py"
expected_base=415d203f2752ddfccfe1963efd17cfd0483565fab592172b6c6ab5f323aa202d
expected_rewriter=bad2362605ae40ad4f88da197bec2bb0dd7e6878da7e3f13e6a22361319025fc
expected_runtime_verifier=be7aef4a7d0c533ae4dde7eef4d89f19af9c7d807782cf50a12e08367490b92a
expected_source=54665a2a7c11a7d4392cf4c809cca93c53596da06fc675dc59cb9430484d0697

derive() {
  Q38_A40_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client
}

[[ $# == 0 ]] || { printf 'FAIL: A41 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$runtime_verifier" | cut -d' ' -f1)" == "$expected_runtime_verifier" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A41 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A41_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
