#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a28-profile.sh"
rewriter="${script_dir}/rewrite-q38-a28-to-a33-fullgraph.py"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a33-fullgraph.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a33-fullgraph-client.sh"
expected_base=4c51385f6cdfa776181ac3ffd9db090f8cb699a5c6ffa989e49cd2672bd27441
expected_rewriter=4ba75fb0eb0311b3feed20072fdceb30802c7425737b9405d22febcbd6b990aa
expected_wrapper=776f608eee77fb8ad4b5d02496e9e68fa4e16392639e0fa471c857de5fffe02e
expected_client=034b08e0eea247c98715646e2211c1507c4b435a06e5ba94703e12784d4e5ce1
expected_source=46418d212b9e162bdee5e7914dc1cfda0d3699bfea14d746f5b66869fe1b925c

derive() {
  Q38_A28_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor \
    --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"
}

[[ $# == 0 ]] || { printf 'FAIL: A33 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]]
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A33 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A33_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
