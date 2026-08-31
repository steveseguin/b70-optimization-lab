#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8-client.sh"
expected_base=28e89555634fe22a06cf87d8bc15fbb69fe6230981ddaef34d9a7fe1476b6981
current_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9
expected_source=1a64bcde010e40b3240beb7152379ea1f185cfef55cc47c2726e99c365fd90d4

derive() {
  Q38_A29_SOURCE_ONLY=1 "$base" | awk -v current_vllm="$current_vllm" '
{
  gsub(/ple-only-a29-moe-m1-warps8/, "ple-only-a31-moe-m1-current")
  gsub(/q38-mtp0-ple-only-a29/, "q38-mtp0-ple-only-a31")
  gsub(/q38-ple-only-a29/, "q38-ple-only-a31")
  gsub(/attempt29/, "attempt31")
  gsub(/19701/, "19703")
  gsub(/A29/, "A31")
  gsub(/d14396e27247c1b251da0ce24a0942772c4b002f/, current_vllm)
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A31 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: A31 base client drifted\n' >&2
  exit 1
}
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A31 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A31_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
