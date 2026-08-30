#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a16-trace.sh"
expected_base=0b5482ab292bf8f054fab026ad9a3c9eef9ef4a7522c17a74a16677b317f7f2b
expected_source=6fbeb749563f4459c9efb105f1c8d3b60a4f2eb7b6ad79dec98aedbca04e5b0c

derive() {
  Q38_A16_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a16/, "ple-only-a17")
  gsub(/q38-ple4k-a16/, "q38-ple4k-a17")
  gsub(/attempt16/, "attempt17")
  gsub(/ATTEMPT=16 PORT=19688/, "ATTEMPT=17 PORT=19689")
  gsub(/19688/, "19689")
  gsub(/Q38_A16_VALIDATE_ONLY/, "Q38_A17_VALIDATE_ONLY")
  if ($0 == "expected_derived=274372861adf49f0a1a9506012a9047357c1eff572f8afadb24fc77b6d62356c")
    print "expected_derived=1174516b5af48f82c39073a6ec1ed66d0a0588420fd7bf11548f7d284c1ef83c"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A17 trace launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A17 trace launcher source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A17_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
