#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a18-trace.sh"
expected_base=7eefe8f6ec91def8d3cc31abc02595428969c1bad68371a8aaa73a55d5ae9dbe
expected_source=2cdd2bad1d80c7fc2b8694f7598fc613414d6b5e5eabd47c1e3bdd24252ce4c5

derive() {
  Q38_A18_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a18/, "ple-only-a19")
  gsub(/attempt18/, "attempt19")
  gsub(/19690/, "19691")
  gsub(/6096391b290369596308e850db622150fc7fc96973d421bbaf8cb19d82046407/, "e93510a3e6b21ec9f0782783653d502ab4c3c7cad98f072f473a849c4b70ce5f")
  gsub(/87597d379d9543af956ed67f4392eb822de0b403604055482aa7d03a53f65a36/, "b2fc8181b4877c0c05e0aca9dc52800aec866e44be25054657e107338bd8f5ef")
  gsub(/Q38_A18_VALIDATE_ONLY/, "Q38_A19_VALIDATE_ONLY")
  if ($0 == "expected_derived=8c527b18bb4074c527b890da0e38e5a9c21b877fa9770be2b7fc887999043b6d")
    print "expected_derived=56104edf1ec95c10c56ef33aec7bda05fc0562e9ff3f2bd3142c160ad0264b9a"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A19 trace supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A19 trace supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A19_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
