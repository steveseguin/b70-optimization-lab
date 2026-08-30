#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a16-trace-client.sh"
expected_base=171816212130fdc0453bf27f576015c88575c45ff87da8543f6cbe0608a6a4ac
expected_source=d3f2b7d7c320a856b4221ec7d76c5aa71959bb74080d94609e607ea0b300ec15

derive() {
  Q38_A16_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a16/, "ple-only-a17")
  gsub(/attempt16/, "attempt17")
  gsub(/19688/, "19689")
  gsub(/Q38_A16_VALIDATE_ONLY/, "Q38_A17_VALIDATE_ONLY")
  if ($0 == "expected_derived=679db6d670d92041db7ab9f28d2dab5f12640fd6cc871e3b8feca66c4f879405")
    print "expected_derived=0cd2e666141987fb882a9fd4e6cae185b4abc4aa1be1d6d0366ada985859566c"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A17 trace client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A17 trace client source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A17_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
