#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a26-async-uva.sh"
profile_wrapper="${script_dir}/vllm-serve-with-q38-a28-profiler.py"
expected_base=30228163b05a5150db1bc3326fab079c7a31241d05d7143ce04159702989e1be
expected_profile_wrapper=b2093aaf3c8cd8310918e019095d34b60c9acaf07d8b9fa5a1f8e577acf9ac15
expected_source=51162888fb165e8b6baf4f1b251f3bc5d3c5318c216efb2ec4de76ee782f8df6
profile_dir=/mnt/fast-ai/q38-profiles/attempt28

derive() {
  Q38_A26_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a26-async-uva/, "ple-only-a28-profile")
  gsub(/q38-ple4k-a26/, "q38-ple4k-a28")
  gsub(/attempt26/, "attempt28")
  gsub(/ATTEMPT=26 PORT=19698/, "ATTEMPT=28 PORT=19700")
  gsub(/19698/, "19700")
  gsub(/Q38_A26_VALIDATE_ONLY/, "Q38_A28_VALIDATE_ONLY")
  gsub(/A26/, "A28")
  gsub(/async-uva-ple-trace-off/, "target-step-xpu-profile")
  if ($0 == "expected_derived=1a3de0d9207843bcb451abfae0d6eadc03debfc87d916bab801db5efae938870")
    print "expected_derived=4a738f678c06707644e3ac5b89d76631e5ba8d61d0a9637887663ef400445905"
  else if ($0 == "  print \"export VLLM_XPU_PLE_UVA_PREFETCH=1\"")
    print "  print \"unset VLLM_XPU_PLE_UVA_PREFETCH\""
  else if ($0 == "export VLLM_XPU_PLE_UVA_PREFETCH=1")
    print "unset VLLM_XPU_PLE_UVA_PREFETCH"
  else if ($0 == "export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm") {
    print "export VLLM_BIN=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/vllm-serve-with-q38-a28-profiler.py"
    print "export Q38_A28_PROFILE_DIR=/mnt/fast-ai/q38-profiles/attempt28"
  } else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A28 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$profile_wrapper" | cut -d' ' -f1)" == "$expected_profile_wrapper" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A28 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A28_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
if [[ "${Q38_A28_VALIDATE_ONLY:-0}" != 1 ]]; then
  [[ ! -e "$profile_dir" ]] || { printf 'FAIL: refusing to reuse %s\n' "$profile_dir" >&2; exit 1; }
  mkdir -p "$profile_dir"
fi
source <(derive)
