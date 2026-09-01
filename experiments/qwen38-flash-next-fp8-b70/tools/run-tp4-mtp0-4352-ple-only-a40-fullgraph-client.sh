#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a39-fullgraph-client.sh"
rewriter="${script_dir}/rewrite-q38-a39-to-a40-fullgraph.py"
runtime_verifier="${script_dir}/verify-q38-a37-fullgraph-runtime.py"
expected_base=d7599824c4a31bf33e1de17e6f99312e3f7f98711f544716ed9614e99ab4dffb
expected_rewriter=a364ba047a24fcf985476ffc91d12f35e68c3b55836397548e330f3551446194
expected_runtime_verifier=be7aef4a7d0c533ae4dde7eef4d89f19af9c7d807782cf50a12e08367490b92a
expected_source=49f7b5e7c6e0f5ee4e498c94aa4bec31b8a8bd5b1b7ff642abc947ab60dba9cb

derive() {
  Q38_A39_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client
}

[[ $# == 0 ]] || { printf 'FAIL: A40 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$runtime_verifier" | cut -d' ' -f1)" == "$expected_runtime_verifier" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A40 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A40_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
