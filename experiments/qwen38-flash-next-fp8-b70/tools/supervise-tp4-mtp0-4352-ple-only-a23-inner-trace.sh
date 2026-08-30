#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a22-inner-trace.sh"
expected_base=3fc2400b9fd3d7c872175165b22e4ca2871a0639ce31899663cda4e49b5dd13d
expected_source=0d529335ef8ae3d450c4a50519210e45100eeffaa89d2e01b8aeebf79146b623

derive() {
  Q38_A22_SOURCE_ONLY=1 "$base" | awk '
{
  if (index($0, ".identity.kv_cache_memory_bytes") && index($0, "print"))
    print "  print \"         .identity.diagnostics == \\\"qwen4exp-ple-inner-trace-rank-all\\\" and\""
  gsub(/ple-only-a22/, "ple-only-a23")
  gsub(/attempt22/, "attempt23")
  gsub(/19694/, "19695")
  gsub(/18889ab0e8a8602bd02a22f775a903eafcc9ac4d2bd01db2ac0f102a9edc3c60/, "9194d3065d2c6ad1fd0e86e6054d0dd398f3d2510f098090c0c06562bfe04874")
  gsub(/65c5dd11b4beb5d2d5796700cb071d25edcffe28dbe00c3b719ac3cb4602da84/, "04cee0d187065cdbcbd3a24195163f93e448c465324b71488bf4720c06fd9f8d")
  gsub(/q38-ple4k-a22-rpc/, "q38-ple4k-a23-rpc")
  gsub(/613afcc501331aa6ff7d5a238a6c9a5d45777b3e/, "f69a0ef46338f93636671c87caa527b3ac2ca129")
  gsub(/Q38_A22_VALIDATE_ONLY/, "Q38_A23_VALIDATE_ONLY")
  if ($0 == "expected_derived=8494ab627ffa8b8e07f73120388ce779cafb89da0f65d487b220318d585df031")
    print "expected_derived=0a08c20662b0e031e4a2c222219e4d8d4e5cf20ffa37a7a1163d2190648ddc49"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A23 inner-trace supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A23 supervisor source %s\n' "$actual_source" >&2; exit 1; }
if [[ "${Q38_A23_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
