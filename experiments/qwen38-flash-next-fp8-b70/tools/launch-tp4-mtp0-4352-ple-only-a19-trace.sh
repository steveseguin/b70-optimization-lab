#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a18-trace.sh"
expected_base=6096391b290369596308e850db622150fc7fc96973d421bbaf8cb19d82046407
expected_source=4226fcdec049ce0601c729438bba0449206919ee67f5d68820cd427d493a7c73

derive() {
  Q38_A18_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a18/, "ple-only-a19")
  gsub(/q38-ple4k-a18/, "q38-ple4k-a19")
  gsub(/attempt18/, "attempt19")
  gsub(/ATTEMPT=18 PORT=19690/, "ATTEMPT=19 PORT=19691")
  gsub(/19690/, "19691")
  gsub(/Q38_A18_VALIDATE_ONLY/, "Q38_A19_VALIDATE_ONLY")
  if ($0 == "expected_derived=f45f2e37922d65660aa4a229b150a8408bd8be0b0d1ebfc87ecda95ed3653546")
    print "expected_derived=1338edcca066adcceec4ee1ea9082f24bf0d1d746ca28ceb7dcee1c1af7a7647"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A19 trace launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A19 trace launcher source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A19_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
