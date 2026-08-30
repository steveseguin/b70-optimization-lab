#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a14-client.sh"
expected_base=2ea92230e4be419a38e89c67fecb60c173a89f1541e7a98c2fbc9d3a251db8b6
expected_source=4ff5d6df5b3fcede4ec56d583de8a678a3f1d038a721a951edbb97cd257c6d2e

derive() {
  Q38_A14_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a14/, "ple-only-a15")
  gsub(/attempt14/, "attempt15")
  gsub(/19686/, "19687")
  gsub(/Q38_A14_VALIDATE_ONLY/, "Q38_A15_VALIDATE_ONLY")
  if ($0 == "expected_derived=5fcdde534fce8228e38ba0bad704be580eced518f72cdef96f075041091fc24b")
    print "expected_derived=d1edfad91a5d7f63f47f629d779a071d72bf28c70fd07f00f84bec71e27c8c40"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A15 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A15 client source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A15_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
