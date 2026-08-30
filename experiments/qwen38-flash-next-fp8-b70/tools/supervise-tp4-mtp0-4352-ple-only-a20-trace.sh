#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a19-trace.sh"
expected_base=76be34e4bd6198ae9183c79d458dd09ded9c8071ac5a50214308d29a1938e76b
expected_source=87e80a6ce1db88535738a2d89daba23439c5fd32a30e334569ead22addd4f691

derive() {
  Q38_A19_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/launch-tp4-mtp0-4352-ple-only-a19-trace\.sh/, "launch-tp4-mtp0-4352-ple-only-a20-external-trace.sh")
  gsub(/run-tp4-mtp0-4352-ple-only-a19-trace-client\.sh/, "run-tp4-mtp0-4352-ple-only-a20-external-trace-client.sh")
  gsub(/ple-only-a19/, "ple-only-a20")
  gsub(/attempt19/, "attempt20")
  gsub(/19691/, "19692")
  gsub(/e93510a3e6b21ec9f0782783653d502ab4c3c7cad98f072f473a849c4b70ce5f/, "efff9bf04d9b45afda80d0a80be8908c07901a51cc5e088f265cc54aebf5bffb")
  gsub(/b2fc8181b4877c0c05e0aca9dc52800aec866e44be25054657e107338bd8f5ef/, "399546be606a48170f6b00dc6968cf7dabe75f2b0a4233f1d96accf8840f066f")
  gsub(/Q38_A19_VALIDATE_ONLY/, "Q38_A20_VALIDATE_ONLY")
  if ($0 == "expected_derived=56104edf1ec95c10c56ef33aec7bda05fc0562e9ff3f2bd3142c160ad0264b9a")
    print "expected_derived=41ad18dd59d79c85ec1838c9a47522e9c9eeb31ca12a801d58754ea7f02c6c06"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A20 external trace supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A20 supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A20_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
