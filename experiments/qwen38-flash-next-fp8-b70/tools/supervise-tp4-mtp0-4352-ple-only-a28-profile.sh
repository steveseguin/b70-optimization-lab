#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a26-async-uva.sh"
expected_base=082c41949dd050fd6c1d95a0e3f8374df03f4f6b98ebbab432c80153b55ebcd8
expected_source=74a9ef659de1368f8dcef0bcbfdb048e783a033ec67c719dc0ce087587a55536

derive() {
  Q38_A26_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a26-async-uva/, "ple-only-a28-profile")
  gsub(/q38-mtp0-ple-only-a26/, "q38-mtp0-ple-only-a28")
  gsub(/q38-ple4k-a26/, "q38-ple4k-a28")
  gsub(/attempt26/, "attempt28")
  gsub(/19698/, "19700")
  gsub(/async-uva-ple-trace-off/, "target-step-xpu-profile")
  if ($0 == "expected_wrapper=30228163b05a5150db1bc3326fab079c7a31241d05d7143ce04159702989e1be") {
    print "expected_wrapper=492ac0b7cfb0d6f4c64fc2bd1e5ab1ec45222d2dd8ce118f50daeb0dce48f934"
    next
  }
  if ($0 == "expected_client=3c5ebbf7182fe6bfb8c516f2f75e83d749dc98d18b9c3885330b4e9024e5e7d0") {
    print "expected_client=1733790e88afca40409fdfab08d629da6b9e5de4e849dabb897b0fd77625d7cb"
    next
  }
  if ($0 == "         .identity.async_uva_ple_prefetch == true and") {
    print "         .identity.async_uva_ple_prefetch == false and"
    print "         .identity.profiler == \"torch_xpu_report_only\" and"
    print "         .identity.profile_delay_iterations == 65 and"
    print "         .identity.profile_max_iterations == 4 and"
    next
  }
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A28 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A28 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A28_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
