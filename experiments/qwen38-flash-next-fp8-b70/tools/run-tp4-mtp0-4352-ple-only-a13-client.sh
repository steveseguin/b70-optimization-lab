#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a10-client.sh"
expected_base=b11ce44155577d78b63451733218e48181c8c24155a8d72f0ca0a6267df5b707
expected_source=a7be5d90e8228ba8425c969216895d9ea2a1fa73a89fba469d58b2065a1bb05c

derive() {
  Q38_A10_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a10/, "ple-only-a13")
  gsub(/attempt10/, "attempt13")
  gsub(/19682/, "19685")
  gsub(/Q38_A10_VALIDATE_ONLY/, "Q38_A13_VALIDATE_ONLY")
  gsub(/e5137bfd8ca2ca718c4fd93d86d54bb843e2999b/, "f68c9386fe5af54055bdf20684b269b9c1340e44")
  gsub(/ple-only-fresh-summary/, "ple-only-qsa-stable-summary")
  gsub(/PLE-only 4K MTP0 fresh-server repeat/, "PLE-only 4K MTP0 QSA-stable treatment")
  if ($0 == "expected_derived=0204b4d184555915f61f1b870b937b2648712232dbb59d2d3cb56023dba12958")
    print "expected_derived=28f0fa3dab983342f63f0ba0c3049a629fc337fe7d03a8e61b0f0f43af45cc44"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A13 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A13 client source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A13_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
