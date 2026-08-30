#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a17-trace.sh"
expected_base=083b0af6b0632ab547cc86553bec19104386fae1cb73da791baf9957ecfeddc0
expected_source=61193bfd7469027ce66247d241fafbb218d25f3658d6089d0f87c5b5c3971ed8

derive() {
  Q38_A17_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a17/, "ple-only-a18")
  gsub(/q38-ple4k-a17/, "q38-ple4k-a18")
  gsub(/attempt17/, "attempt18")
  gsub(/ATTEMPT=17 PORT=19689/, "ATTEMPT=18 PORT=19690")
  gsub(/19689/, "19690")
  gsub(/Q38_A17_VALIDATE_ONLY/, "Q38_A18_VALIDATE_ONLY")
  if ($0 == "expected_derived=1174516b5af48f82c39073a6ec1ed66d0a0588420fd7bf11548f7d284c1ef83c")
    print "expected_derived=f45f2e37922d65660aa4a229b150a8408bd8be0b0d1ebfc87ecda95ed3653546"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A18 trace launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A18 trace launcher source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A18_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
