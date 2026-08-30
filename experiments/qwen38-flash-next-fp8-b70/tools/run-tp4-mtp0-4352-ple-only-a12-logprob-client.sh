#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a11-logprob-client.sh"
expected_base=56740bfb3662ce2674a367c9b43c2474379cc664b9d80da353117e99355eea07
expected_source=8892b1c72b1240dc32d8696eb3cb36d35f75f554a8333fb9af74a07480e0e816

derive() {
  awk '
index($0, "repo=/home/steve/llm-optimizations") == 1 { print; next }
$0 == "[[ \"$(sha256sum \"$launcher\" | cut -d'\'' '\'' -f1)\" == 955505783af6ec3fbfe884c3a0134561d52d0597bc7dc65a94436013a9cbd225 ]]" {
  print "[[ \"$(sha256sum \"$launcher\" | cut -d'\'' '\'' -f1)\" == f2d652635bef135f59f3e5700ee0320ba3c2cff3986b3787f2445b3851408f66 ]]"; next
}
$0 == "[[ \"$(sha256sum \"$probe\" | cut -d'\'' '\'' -f1)\" == 95a03d9c134168a2468957d7775bcb4e14df8fccb4d14ea9f596e99196edba4f ]]" {
  print "[[ \"$(sha256sum \"$probe\" | cut -d'\'' '\'' -f1)\" == 7608299f95fbec2067011414ad12322f0fad56a621e0e63105f8964d57ca956f ]]"; next
}
{
  gsub(/a11-logprob/, "a12-logprob")
  gsub(/attempt11/, "attempt12")
  gsub(/19683/, "19684")
  print
}
' "$base"
}

[[ $# == 0 ]] || { printf 'FAIL: A12 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A12 client source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A12_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
