#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a17-trace-client.sh"
expected_base=3d52f02efe0794a76ed1eb12311299126612b86dc3cbd3062df1d8fcdd0ba7c9
expected_source=141fbe09c8b27eb5183131ab82d8d64380f6018e2370bdc0c1ee5a00a84f1097

derive() {
  Q38_A17_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a17/, "ple-only-a18")
  gsub(/attempt17/, "attempt18")
  gsub(/19689/, "19690")
  gsub(/Q38_A17_VALIDATE_ONLY/, "Q38_A18_VALIDATE_ONLY")
  if ($0 == "expected_derived=0cd2e666141987fb882a9fd4e6cae185b4abc4aa1be1d6d0366ada985859566c")
    print "expected_derived=f2066bdfdc7b7596d08e704c9b522c9317993c17763f1651d63b83f43735e9a3"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A18 trace client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A18 trace client source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A18_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
