#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a34-fullgraph-client.sh"
rewriter="${script_dir}/rewrite-q38-a34-to-a35-fullgraph.py"
runtime_verifier="${script_dir}/verify-q38-a34-fullgraph-runtime.py"
expected_base=cf9b044839c5027f57bc74982328adf969c131921aba3b222704b269285da247
expected_rewriter=037c4c7e4acdfa8ac621ff55bb114d027669598e7237a8699bd544f9d4f76375
expected_runtime_verifier=679512374ece0b5ee48d9f48185e2abd24e251fe6dfcceb6eb891e545ef28747
expected_source=bfd6a1a2b3e7f2564de1cbc7850772cf1ce5923283422f2741fe4e25b3e16c8a

derive() {
  Q38_A34_SOURCE_ONLY=1 "$base" | python3 "$rewriter" client
}

[[ $# == 0 ]] || { printf 'FAIL: A35 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$runtime_verifier" | cut -d' ' -f1)" == "$expected_runtime_verifier" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A35 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A35_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
