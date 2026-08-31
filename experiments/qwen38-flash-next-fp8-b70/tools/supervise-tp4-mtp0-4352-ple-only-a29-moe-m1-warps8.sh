#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a27-moe-warps8.sh"
expected_base=0baede0a853c984df8994fd4f18fe08eb1d0d97c9bafa67d2f79d9953c436b44
expected_wrapper=6a624362e1ae1d4c4522fbc6cd88c6ac9e7da0da7998390c28333927c3aec5b0
expected_client=28e89555634fe22a06cf87d8bc15fbb69fe6230981ddaef34d9a7fe1476b6981
expected_source=f29972e743ff0e115b36050bd9ac44328bc37fe60f2888aeadc4f3129d1bb612

derive() {
  Q38_A27_SOURCE_ONLY=1 "$base" | awk -v wrapper_hash="$expected_wrapper" -v client_hash="$expected_client" '
{
  gsub(/ple-only-a27-moe-warps8/, "ple-only-a29-moe-m1-warps8")
  gsub(/q38-mtp0-ple-only-a27/, "q38-mtp0-ple-only-a29")
  gsub(/q38-ple4k-a27/, "q38-ple4k-a29")
  gsub(/attempt27/, "attempt29")
  gsub(/19699/, "19701")
  gsub(/moe-warps8-m4-trace-off/, "moe-m1-warps8-selected-trace-off")
  gsub(/f93b5e1d5863e04268eb96877ab2ef6ba0990c42c62f1dff27bc36676c30bf7f/, "91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464")
  if ($0 == "expected_wrapper=caf12747ccd194ce784c7f64f3bbd327ed63fbfc3d2a7b92d702e5162ec58e0f") {
    print "expected_wrapper=" wrapper_hash
    next
  }
  if ($0 == "expected_client=d3cb538d71f11423b8cc5f13a2ca9873fb9ad1cf1a654eaaa6ddac7f480cf68a") {
    print "expected_client=" client_hash
    next
  }
  if ($0 == "         .identity.moe_m4_num_warps == 8 and") {
    print "         .identity.moe_selected_batch_key == 1 and"
    print "         .identity.moe_m1_num_warps == 8 and"
    next
  }
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A29 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A29 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A29_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
