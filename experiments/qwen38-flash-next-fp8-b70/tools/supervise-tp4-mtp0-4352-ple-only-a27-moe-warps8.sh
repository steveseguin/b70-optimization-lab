#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a26-async-uva.sh"
expected_base=082c41949dd050fd6c1d95a0e3f8374df03f4f6b98ebbab432c80153b55ebcd8
expected_source=e51c4e9e5f027077ee90ea4a214459e1430eaadd24a89725fa8ea3c8444fa852

derive() {
  Q38_A26_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a26-async-uva/, "ple-only-a27-moe-warps8")
  gsub(/q38-mtp0-ple-only-a26/, "q38-mtp0-ple-only-a27")
  gsub(/q38-ple4k-a26/, "q38-ple4k-a27")
  gsub(/attempt26/, "attempt27")
  gsub(/19698/, "19699")
  gsub(/async-uva-ple-trace-off/, "moe-warps8-m4-trace-off")
  if ($0 == "expected_wrapper=30228163b05a5150db1bc3326fab079c7a31241d05d7143ce04159702989e1be") {
    print "expected_wrapper=caf12747ccd194ce784c7f64f3bbd327ed63fbfc3d2a7b92d702e5162ec58e0f"
    next
  }
  if ($0 == "expected_client=3c5ebbf7182fe6bfb8c516f2f75e83d749dc98d18b9c3885330b4e9024e5e7d0") {
    print "expected_client=d3cb538d71f11423b8cc5f13a2ca9873fb9ad1cf1a654eaaa6ddac7f480cf68a"
    next
  }
  if ($0 == "         .identity.async_uva_ple_prefetch == true and") {
    print "         .identity.async_uva_ple_prefetch == false and"
    print "         .identity.moe_m4_num_warps == 8 and"
    print "         .identity.tuned_config_sha256 == \"f93b5e1d5863e04268eb96877ab2ef6ba0990c42c62f1dff27bc36676c30bf7f\" and"
    next
  }
  print
}
' 
}

[[ $# == 0 ]] || { printf 'FAIL: A27 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A27 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A27_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
