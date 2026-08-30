#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a11-logprob.sh"
expected_base=44d154df0dc163b9a46257e264ea34b5291803b1d6a892398bf8856b3fe4fd70
expected_source=e2957acf73d46954ca86f01028cc759ae965f0c56b8e6d8b2ea2100fa8df0627

derive() {
  Q38_A11_SOURCE_ONLY=1 "$base" | awk '
$0 == "expected_wrapper=955505783af6ec3fbfe884c3a0134561d52d0597bc7dc65a94436013a9cbd225" {
  print "expected_wrapper=f2d652635bef135f59f3e5700ee0320ba3c2cff3986b3787f2445b3851408f66"; next
}
$0 == "expected_client=56740bfb3662ce2674a367c9b43c2474379cc664b9d80da353117e99355eea07" {
  print "expected_client=5756b9eb40ef9451a20be0d66c16c7ea9cf00f74ac8936cf8242b88f196988da"; next
}
{
  gsub(/a11-logprob/, "a12-logprob")
  gsub(/attempt11/, "attempt12")
  gsub(/19683/, "19684")
  gsub(/q38-ple4k-a11-logprob-rpc/, "q38-ple4k-a12-logprob-rpc")
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A12 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A12 supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A12_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
