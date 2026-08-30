#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a9.sh"
expected_base=0cab8bb2845209a9302d37634acf633dd0b5f67b7cfd4df1fecf4cffbc971da2
expected_source=045f86e19980d542eca898a9880a81ba48135e7d26eeb5b6aae76833fb10c75c

derive() {
  awk '
index($0, "script_dir=$(cd --") == 1 {
  print "script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools"; next
}
$0 == "expected_derived=7c3adf6a9b0c551e61d1489d78102af1208b2084d18c1522cb2fd667131c3726" {
  print "expected_derived=31c29c1905bd98783988291e69013d9740312092dccc51c43cd94b463c809c32"; next
}
index($0, "print \"expected_wrapper=9fb4751df8641fdac67a7836becd025bf314c8e8a79c30c876b73c09c859cfa4\"") {
  print "  print \"expected_wrapper=8a693f850bb43e71f41258b9cd80915c6275c0f590ef12b6e3ed7c5d9e09a910\"; next"; next
}
index($0, "print \"expected_client=71595fc912078203087fc04ab3a1a944589af91dd3855c2f5b8c086de7cb4b9c\"") {
  print "  print \"expected_client=b11ce44155577d78b63451733218e48181c8c24155a8d72f0ca0a6267df5b707\"; next"; next
}
{
  gsub(/ple-only-a9/, "ple-only-a10")
  gsub(/attempt9/, "attempt10")
  gsub(/19681/, "19682")
  gsub(/q38-ple4k-a9-rpc/, "q38-ple4k-a10-rpc")
  gsub(/ple-only-summary/, "ple-only-fresh-summary")
  gsub(/PLE-only 4K MTP0 candidate/, "PLE-only 4K MTP0 fresh-server repeat")
  gsub(/Q38_A9_VALIDATE_ONLY/, "Q38_A10_VALIDATE_ONLY")
  print
}
' "$base"
}

[[ $# == 0 ]] || { printf 'FAIL: A10 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A10 supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A10_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
