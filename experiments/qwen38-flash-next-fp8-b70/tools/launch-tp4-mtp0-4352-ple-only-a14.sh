#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a13.sh"
expected_base=2b9557fd9713abe75e6a89d6ee5068f15520e9cc919e11de687dff07c292f7ad
expected_source=2020d843565fc88a80242f042a4ba7607cfbcfc114f125a4b973fd79a19adb3b

derive() {
  Q38_A13_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a13/, "ple-only-a14")
  gsub(/q38-ple4k-a13/, "q38-ple4k-a14")
  gsub(/attempt13/, "attempt14")
  gsub(/ATTEMPT=13 PORT=19685/, "ATTEMPT=14 PORT=19686")
  gsub(/19685/, "19686")
  gsub(/Q38_A13_VALIDATE_ONLY/, "Q38_A14_VALIDATE_ONLY")
  if ($0 == "expected_derived=2e5992bde342379a08cff4e22d067dbab423966829def1c508b770fe83250b57")
    print "expected_derived=0c6e4c11f3ff0b2ae88d7a8437ca17c9987534b6109b2598979049351986e4cb"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A14 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A14 launcher source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A14_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
