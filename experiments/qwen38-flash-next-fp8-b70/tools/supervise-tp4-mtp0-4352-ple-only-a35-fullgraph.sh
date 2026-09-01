#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a34-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a34-to-a35-fullgraph.py"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a35-fullgraph.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a35-fullgraph-client.sh"
expected_base=2b5e8dcf7e1ea2030b4f4a4083318f30ff35d2db7caaed83981e2123f7daf607
expected_rewriter=037c4c7e4acdfa8ac621ff55bb114d027669598e7237a8699bd544f9d4f76375
expected_wrapper=8cea3b85a3aa332e46e35eacfdf2096e59a760343fb21d042f819442c4b8a11f
expected_client=264c27d0fb014f6a7340f392b70df84e7250f04a71f91eab2570965ba4c10bf5
expected_source=68978d991d533f592e5cf3a2c44dc8c98b475dccbb96e3ce6628de0893a45a2b

derive() {
  Q38_A34_SOURCE_ONLY=1 "$base" | python3 "$rewriter" supervisor \
    --wrapper-hash "$expected_wrapper" --client-hash "$expected_client"
}

[[ $# == 0 ]] || { printf 'FAIL: A35 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]]
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A35 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A35_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
