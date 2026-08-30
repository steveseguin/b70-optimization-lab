#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a9.sh"
expected_base=9fb4751df8641fdac67a7836becd025bf314c8e8a79c30c876b73c09c859cfa4
expected_source=f1b05e48bd2d0d6bab7a147c0179f57f2ae8913bcb56505b45873f3759e0e834

derive() {
  awk '
index($0, "script_dir=$(cd --") == 1 {
  print "script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools"; next
}
$0 == "derived=/tmp/q38-ple4k-a9-base.sh" { print "derived=/tmp/q38-ple4k-a11-logprob-base.sh"; next }
$0 == "expected_derived=973e14f4d94a58ec3551f2589b991cd62f410bf5bc93d399a194bbc7412edff0" {
  print "expected_derived=39de9c53ee134eea0e53df0f6c4b771ae45edc0661f1a9ce0ce493b288f99b86"; next
}
index($0, "print \"rpc_dir=/tmp/q38-ple4k-a9-rpc\"") {
  gsub(/q38-ple4k-a9-rpc/, "q38-ple4k-a11-logprob-rpc"); print; next
}
index($0, "grep -Fxq '\''rpc_dir=/tmp/q38-ple4k-a9-rpc'\''") {
  gsub(/q38-ple4k-a9-rpc/, "q38-ple4k-a11-logprob-rpc"); print; next
}
$0 == "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=9 PORT=19681" {
  print "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=11 PORT=19683"; next
}
index($0, "Q38_A9_VALIDATE_ONLY") { gsub(/Q38_A9_VALIDATE_ONLY/, "Q38_A11_VALIDATE_ONLY"); print; next }
{ print }
' "$base"
}

[[ $# == 0 ]] || { printf 'FAIL: A11 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A11 launcher source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A11_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
