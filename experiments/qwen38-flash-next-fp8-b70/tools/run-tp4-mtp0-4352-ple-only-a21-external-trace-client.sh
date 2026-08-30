#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a20-external-trace-client.sh"
expected_base=399546be606a48170f6b00dc6968cf7dabe75f2b0a4233f1d96accf8840f066f
expected_source=3362301864d8f031c90323d8266197ef7d89edf596778a5529dfa311d5cc17d5

derive() {
  Q38_A20_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a20/, "ple-only-a21")
  gsub(/attempt20/, "attempt21")
  gsub(/19692/, "19693")
  gsub(/Q38_A20_VALIDATE_ONLY/, "Q38_A21_VALIDATE_ONLY")
  if ($0 == "expected_derived=a1feb6d4e293873e6b494de30da4bcd280993aaad158db4fb400f33b8c9a8102")
    print "expected_derived=552f707886836de9a5d74741a8eb081c4c140cfb767bda21eb7c8edecaa1962b"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A21 external trace client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || exit 1
if [[ "${Q38_A21_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
