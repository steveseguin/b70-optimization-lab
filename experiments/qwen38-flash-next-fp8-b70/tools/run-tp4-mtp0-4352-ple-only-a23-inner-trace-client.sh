#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a22-inner-trace-client.sh"
expected_base=65c5dd11b4beb5d2d5796700cb071d25edcffe28dbe00c3b719ac3cb4602da84
expected_source=91389d2ca017dd3f0d657b1a5822426780a22c47b9541038b4640a077286ed80

derive() {
  Q38_A22_SOURCE_ONLY=1 "$base" | awk '
{
  if ($0 == "  gsub(/8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de/, \"268f6de4a3e4353191d4f75c48b6b0f243ca30196fcb4c582e1db2e2935db656\")")
    print "  gsub(/diagnostics=none/, \"diagnostics=qwen4exp-ple-inner-trace-rank-all\")"
  if (index($0, "input_embedding") && index($0, "kv_cache_memory_bytes"))
    print "  print \"        \\\"diagnostics\\\": \\\"qwen4exp-ple-inner-trace-rank-all\\\",\""
  gsub(/ple-only-a22/, "ple-only-a23")
  gsub(/attempt22/, "attempt23")
  gsub(/19694/, "19695")
  gsub(/613afcc501331aa6ff7d5a238a6c9a5d45777b3e/, "f69a0ef46338f93636671c87caa527b3ac2ca129")
  gsub(/Q38_A22_VALIDATE_ONLY/, "Q38_A23_VALIDATE_ONLY")
  if ($0 == "expected_derived=ae0f47a0e4972880d2b93ff91c25c5233360d7343482bcb53d61b964b9d520b1")
    print "expected_derived=aa24172f7f22f46524f29bfcbd6a2dec94a0dfc0299df666bd13c31d3b9f1c7c"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A23 inner-trace client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A23 client source %s\n' "$actual_source" >&2; exit 1; }
if [[ "${Q38_A23_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
