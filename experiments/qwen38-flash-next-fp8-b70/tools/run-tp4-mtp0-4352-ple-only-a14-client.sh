#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a13-client.sh"
expected_base=0240ce9fd347e93d0f1b05087ac65ee26936e9026af573934d835daec05ab0c7
expected_source=772a0fbf4a2a5f00b2bbdafdfee7ee59af4fddb84326b8063101f52b691e3939

derive() {
  Q38_A13_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a13/, "ple-only-a14")
  gsub(/attempt13/, "attempt14")
  gsub(/19685/, "19686")
  gsub(/Q38_A13_VALIDATE_ONLY/, "Q38_A14_VALIDATE_ONLY")
  if ($0 == "expected_derived=28f0fa3dab983342f63f0ba0c3049a629fc337fe7d03a8e61b0f0f43af45cc44")
    print "expected_derived=5fcdde534fce8228e38ba0bad704be580eced518f72cdef96f075041091fc24b"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A14 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A14 client source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A14_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
