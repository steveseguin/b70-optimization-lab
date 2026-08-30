#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a10.sh"
expected_base=8a693f850bb43e71f41258b9cd80915c6275c0f590ef12b6e3ed7c5d9e09a910
expected_source=0c9737215ad76c2e1607144120d45f65be9ed262e98b4d6a1bcb84ab890b2443

derive() {
  Q38_A10_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/q38-ple4k-a10/, "q38-ple4k-a13")
  gsub(/attempt10/, "attempt13")
  gsub(/ATTEMPT=10 PORT=19682/, "ATTEMPT=13 PORT=19685")
  gsub(/19682/, "19685")
  gsub(/Q38_A10_VALIDATE_ONLY/, "Q38_A13_VALIDATE_ONLY")
  gsub(/e5137bfd8ca2ca718c4fd93d86d54bb843e2999b/, "f68c9386fe5af54055bdf20684b269b9c1340e44")
  if ($0 == "expected_derived=4793b1397806f983effddac88f09d96bb4dc53131d408526143d08ec3fbf93c2")
    print "expected_derived=2e5992bde342379a08cff4e22d067dbab423966829def1c508b770fe83250b57"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A13 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A13 launcher source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A13_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
