#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a20-external-trace.sh"
expected_base=efff9bf04d9b45afda80d0a80be8908c07901a51cc5e088f265cc54aebf5bffb
expected_source=23629db3402b89b90cfe7a5ae302869c20ad576c913d4ba56c5b1654855973bf

derive() {
  Q38_A20_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a20/, "ple-only-a21")
  gsub(/q38-ple4k-a20/, "q38-ple4k-a21")
  gsub(/attempt20/, "attempt21")
  gsub(/ATTEMPT=20 PORT=19692/, "ATTEMPT=21 PORT=19693")
  gsub(/19692/, "19693")
  gsub(/Q38_A20_VALIDATE_ONLY/, "Q38_A21_VALIDATE_ONLY")
  if ($0 == "expected_derived=97b2680255034384a794c46159723b7bf44df200b15c8f0f0c9b4bc7764dcbcb")
    print "expected_derived=457cf9cd35de77abc1c51f07702555625a148c19ae7204d27d7bc313bb282a4a"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A21 external trace launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || exit 1
if [[ "${Q38_A21_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
