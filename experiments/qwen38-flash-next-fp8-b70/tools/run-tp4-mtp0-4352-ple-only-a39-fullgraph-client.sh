#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a38-fullgraph-client.sh"
rewriter="${script_dir}/rewrite-q38-a38-to-a39-fullgraph.py"
runtime_verifier="${script_dir}/verify-q38-a37-fullgraph-runtime.py"
expected_base=33a43865033539c699f73ecabdfee41a9bb2ea17e5ad4ffdc0088678d02c5a81
expected_rewriter=232ef59296c75da4b27c9b7ac1779ea7d89751edacad7743f6f2c035fc4d86d6
expected_runtime_verifier=be7aef4a7d0c533ae4dde7eef4d89f19af9c7d807782cf50a12e08367490b92a
expected_source=3f515af85691a3bd00604b0a5f590182a9a00b86ae84f7653cb1df70ef9fa777

derive() {
  Q38_A38_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client
}

[[ $# == 0 ]] || { printf 'FAIL: A39 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$runtime_verifier" | cut -d' ' -f1)" == "$expected_runtime_verifier" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A39 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A39_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
