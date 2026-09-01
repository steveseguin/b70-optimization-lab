#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a33-fullgraph-client.sh"
rewriter="${script_dir}/rewrite-q38-a33-to-a34-fullgraph.py"
runtime_verifier="${script_dir}/verify-q38-a34-fullgraph-runtime.py"
expected_base=034b08e0eea247c98715646e2211c1507c4b435a06e5ba94703e12784d4e5ce1
expected_rewriter=3dfd9bf23e83cd63fdb8eb1d367d9c601bc55d333ba4952869ffa5c778b60a7e
expected_runtime_verifier=679512374ece0b5ee48d9f48185e2abd24e251fe6dfcceb6eb891e545ef28747
expected_source=cc62400eeb859bdb2f2bae456826b30c54194cf9b659b71de7bf605645295418

derive() {
  Q38_A33_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client \
    --runtime-verifier-hash "$expected_runtime_verifier"
}

[[ $# == 0 ]] || { printf 'FAIL: A34 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$runtime_verifier" | cut -d' ' -f1)" == "$expected_runtime_verifier" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A34 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A34_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
