#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a9-client.sh"
expected_base=71595fc912078203087fc04ab3a1a944589af91dd3855c2f5b8c086de7cb4b9c
expected_source=3f30afac7bf46e2d98487d201af4a88831ea5e9ea0fa68199a2ecb536d6bdbc3

derive() {
  awk '
index($0, "script_dir=$(cd --") == 1 {
  print "script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools"; next
}
$0 == "expected_derived=66378542f789ff81d90dd4535156f04663ea72179c28d60442b9a35412858c33" {
  print "expected_derived=0204b4d184555915f61f1b870b937b2648712232dbb59d2d3cb56023dba12958"; next
}
{
  gsub(/ple-only-a9/, "ple-only-a10")
  gsub(/attempt9/, "attempt10")
  gsub(/19681/, "19682")
  gsub(/ple-only-summary/, "ple-only-fresh-summary")
  gsub(/PLE-only 4K MTP0 candidate/, "PLE-only 4K MTP0 fresh-server repeat")
  gsub(/Q38_A9_VALIDATE_ONLY/, "Q38_A10_VALIDATE_ONLY")
  print
}
' "$base"
}

[[ $# == 0 ]] || { printf 'FAIL: A10 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A10 client source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A10_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
