#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a9.sh"
expected_base=9fb4751df8641fdac67a7836becd025bf314c8e8a79c30c876b73c09c859cfa4
expected_source=4d100ebaea97078197278dd3c23de7af0ad511c6597aa7e7b442eb3e3ff69b52

derive() {
  awk '
index($0, "script_dir=$(cd --") == 1 {
  print "script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools"; next
}
$0 == "derived=/tmp/q38-ple4k-a9-base.sh" { print "derived=/tmp/q38-ple4k-a10-base.sh"; next }
$0 == "expected_derived=973e14f4d94a58ec3551f2589b991cd62f410bf5bc93d399a194bbc7412edff0" {
  print "expected_derived=4793b1397806f983effddac88f09d96bb4dc53131d408526143d08ec3fbf93c2"; next
}
index($0, "print \"rpc_dir=/tmp/q38-ple4k-a9-rpc\"") {
  gsub(/q38-ple4k-a9-rpc/, "q38-ple4k-a10-rpc"); print; next
}
index($0, "grep -Fxq '\''rpc_dir=/tmp/q38-ple4k-a9-rpc'\''") {
  gsub(/q38-ple4k-a9-rpc/, "q38-ple4k-a10-rpc"); print; next
}
$0 == "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=9 PORT=19681" {
  print "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=10 PORT=19682"; next
}
index($0, "Q38_A9_VALIDATE_ONLY") { gsub(/Q38_A9_VALIDATE_ONLY/, "Q38_A10_VALIDATE_ONLY"); print; next }
{ print }
' "$base"
}

[[ $# == 0 ]] || { printf 'FAIL: A10 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A10 launcher source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A10_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
