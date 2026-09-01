#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a37-fullgraph-client.sh"
rewriter="${script_dir}/rewrite-q38-a37-to-a38-fullgraph.py"
runtime_verifier="${script_dir}/verify-q38-a37-fullgraph-runtime.py"
expected_base=eb1e81820de1766b8e577dd3296bb800dcbfd7ca60d7e75f33e8ee3dda15bd1c
expected_rewriter=1bf85dd7198d709e1925671dbaa507c330ce5f353e748a32cb4c3784bf1959a1
expected_runtime_verifier=be7aef4a7d0c533ae4dde7eef4d89f19af9c7d807782cf50a12e08367490b92a
expected_source=4ab9e8eddef7942e1d13800d65e94d7640c48d4b78eead271af399f445e8fac6

derive() {
  Q38_A37_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client
}

[[ $# == 0 ]] || { printf 'FAIL: A38 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$runtime_verifier" | cut -d' ' -f1)" == "$expected_runtime_verifier" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A38 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A38_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
