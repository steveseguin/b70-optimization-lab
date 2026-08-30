#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a25-local-inner-trace.sh"
expected_base=b5679192ae6a965ef78196bbad24b17494a8080241d0dab42de39e6e55af3fd3
expected_source=a714713b654f6eb2ca44ca402eab4dab9c26f6cc53e7d1909344c15d8329f1ff

derive() {
  Q38_A25_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a25-local-inner-trace/, "ple-only-a26-async-uva")
  gsub(/q38-mtp0-ple-only-a25/, "q38-mtp0-ple-only-a26")
  gsub(/q38-ple4k-a25/, "q38-ple4k-a26")
  gsub(/attempt25/, "attempt26")
  gsub(/19697/, "19698")
  gsub(/ca20c4465ca34fc733aac70416b75d7cb8a1c46f/, "d14396e27247c1b251da0ce24a0942772c4b002f")
  gsub(/qwen4exp-ple-inner-trace-rank-all/, "async-uva-ple-trace-off")
  if ($0 == "expected_wrapper=170f5d282c52188f803e7112c9d9ca77595a1bb29963a3457b7fe8d03d32e77f") {
    print "expected_wrapper=30228163b05a5150db1bc3326fab079c7a31241d05d7143ce04159702989e1be"
    next
  }
  if ($0 == "expected_client=be4cd1d7f15669a71061e3a7567d796431bc37a624f9026e12eb3418a5818f65") {
    print "expected_client=3c5ebbf7182fe6bfb8c516f2f75e83d749dc98d18b9c3885330b4e9024e5e7d0"
    next
  }
  if ($0 == "         .identity.placement == \"ple_only_uva\" and") {
    print
    print "         .identity.async_uva_ple_prefetch == true and"
    next
  }
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A26 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A26 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A26_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
