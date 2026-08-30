#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a15-client.sh"
expected_base=14c8e29c7bab28fa55b3e52db5092648f7702525220f8041d46840f214a0574f
expected_source=8a361379a8533722ca37dccaba64581605125d3603a7855c0ffac63505223f3e

derive() {
  Q38_A15_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a15/, "ple-only-a16")
  gsub(/attempt15/, "attempt16")
  gsub(/19687/, "19688")
  gsub(/f68c9386fe5af54055bdf20684b269b9c1340e44/, "9f720cd4aa6c8a8b045f54dfa10f5b8611caccbd")
  gsub(/supervise-tp4-mtp0-4352-ple-only-a16\.sh/, "supervise-tp4-mtp0-4352-ple-only-a16-trace.sh")
  gsub(/Q38_A15_VALIDATE_ONLY/, "Q38_A16_VALIDATE_ONLY")
  if ($0 == "expected_derived=d1edfad91a5d7f63f47f629d779a071d72bf28c70fd07f00f84bec71e27c8c40")
    print "expected_derived=679db6d670d92041db7ab9f28d2dab5f12640fd6cc871e3b8feca66c4f879405"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A16 trace client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A16 trace client source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A16_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
