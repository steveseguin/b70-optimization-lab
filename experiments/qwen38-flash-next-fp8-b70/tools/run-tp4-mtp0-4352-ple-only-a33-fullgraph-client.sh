#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a28-profile-client.sh"
rewriter="${script_dir}/rewrite-q38-a28-to-a33-fullgraph.py"
runtime_verifier="${script_dir}/verify-q38-a33-fullgraph-runtime.py"
expected_base=1733790e88afca40409fdfab08d629da6b9e5de4e849dabb897b0fd77625d7cb
expected_rewriter=4ba75fb0eb0311b3feed20072fdceb30802c7425737b9405d22febcbd6b990aa
expected_runtime_verifier=239f80b93531762ee607b2b651b3c69d4ba3d7b888c783ef989d321e7d834fae
expected_source=768b7151038da17e25bb052ea0e6cde7176052eda9d74ab554e86c17eb355894

derive() {
  Q38_A28_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client \
    --runtime-verifier-hash "$expected_runtime_verifier"
}

[[ $# == 0 ]] || { printf 'FAIL: A33 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$runtime_verifier" | cut -d' ' -f1)" == "$expected_runtime_verifier" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A33 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A33_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
