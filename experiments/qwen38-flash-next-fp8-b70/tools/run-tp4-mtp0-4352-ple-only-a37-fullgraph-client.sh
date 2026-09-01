#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a36-fullgraph-client.sh"
rewriter="${script_dir}/rewrite-q38-a36-to-a37-fullgraph.py"
runtime_verifier="${script_dir}/verify-q38-a37-fullgraph-runtime.py"
expected_base=1949bbc71a62847525156d05f73851a3c9b4dab058bc7b4931e2a3dba8604b5f
expected_rewriter=8ce5637d024992d9d3836f7cb6bb322c667e24e6fed09fdabc43024c52307fd3
expected_runtime_verifier=be7aef4a7d0c533ae4dde7eef4d89f19af9c7d807782cf50a12e08367490b92a
expected_source=504c958f54669570d2504492a80eff4530bb345dee89a93b2810c3218c22ac26

derive() {
  Q38_A36_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client \
    --runtime-verifier-hash "$expected_runtime_verifier"
}

[[ $# == 0 ]] || { printf 'FAIL: A37 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$runtime_verifier" | cut -d' ' -f1)" == "$expected_runtime_verifier" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A37 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A37_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
