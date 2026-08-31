#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a26-async-uva.sh"
expected_base=30228163b05a5150db1bc3326fab079c7a31241d05d7143ce04159702989e1be
expected_source=140f4ef932837bca306c176d26e7bd1c45818a821900a14bbddc4171a3fc4561
config_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m4
config_name='E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json'
config_sha=f93b5e1d5863e04268eb96877ab2ef6ba0990c42c62f1dff27bc36676c30bf7f

derive() {
  Q38_A26_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a26-async-uva/, "ple-only-a27-moe-warps8")
  gsub(/q38-ple4k-a26/, "q38-ple4k-a27")
  gsub(/attempt26/, "attempt27")
  gsub(/ATTEMPT=26 PORT=19698/, "ATTEMPT=27 PORT=19699")
  gsub(/19698/, "19699")
  gsub(/Q38_A26_VALIDATE_ONLY/, "Q38_A27_VALIDATE_ONLY")
  gsub(/A26/, "A27")
  gsub(/async-uva-ple-trace-off/, "moe-warps8-m4-trace-off")
  if ($0 == "expected_derived=1a3de0d9207843bcb451abfae0d6eadc03debfc87d916bab801db5efae938870")
    print "expected_derived=54e0f0e2531b95d99c289818da12bda3276cb87de4cb27dc47d69a9e9f0bbd3c"
  else if ($0 == "  print \"export VLLM_XPU_PLE_UVA_PREFETCH=1\"") {
    print "  print \"unset VLLM_XPU_PLE_UVA_PREFETCH\""
    print "  print \"export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m4\""
  } else if ($0 == "export VLLM_XPU_PLE_UVA_PREFETCH=1") {
    print "unset VLLM_XPU_PLE_UVA_PREFETCH"
    print "export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m4"
  } else if (index($0, "status --porcelain") > 0 && index($0, "print") > 0) {
    print
    print "    print \"config_file=\\\"/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m4/E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json\\\"\""
    print "    print \"[[ \\\"$(sha256sum \\\"${config_file}\\\" | cut -c1-64)\\\" == f93b5e1d5863e04268eb96877ab2ef6ba0990c42c62f1dff27bc36676c30bf7f ]] || fail \\\"M4 MoE config changed immediately before launch\\\"\""
  } else
    print
}
' 
}

[[ $# == 0 ]] || { printf 'FAIL: A27 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
config_file="${config_dir}/${config_name}"
[[ "$(sha256sum "$config_file" | cut -d' ' -f1)" == "$config_sha" ]]
[[ "$(jq -r '."4".num_warps' "$config_file")" == 8 ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A27 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A27_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
