#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a26-async-uva-client.sh"
expected_base=3c5ebbf7182fe6bfb8c516f2f75e83d749dc98d18b9c3885330b4e9024e5e7d0
expected_source=8e998276f659fd5d575242dc7afdc752cd04a4e5fc348748bbfab1f653bfcf8c

derive() {
  Q38_A26_SOURCE_ONLY=1 "$base" | awk '
skip_async { if ($0 == "}") skip_async = 0; next }
{
  gsub(/ple-only-a26-async-uva/, "ple-only-a27-moe-warps8")
  gsub(/q38-mtp0-ple-only-a26/, "q38-mtp0-ple-only-a27")
  gsub(/q38-ple-only-a26/, "q38-ple-only-a27")
  gsub(/attempt26/, "attempt27")
  gsub(/19698/, "19699")
  gsub(/async-uva-ple-trace-off/, "moe-warps8-m4-trace-off")
  if (index($0, "grep -zFxq '\''VLLM_XPU_PLE_UVA_PREFETCH=1'\''") == 1) {
    print "if grep -zFq '\''VLLM_XPU_PLE_UVA_PREFETCH='\'' \"/proc/${server_pid}/environ\"; then"
    print "  printf '\''FAIL: async UVA PLE selector unexpectedly present in server environment\\n'\'' >&2"
    print "  exit 1"
    print "fi"
    print "grep -zFxq '\''VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m4'\'' \"/proc/${server_pid}/environ\" || {"
    print "  printf '\''FAIL: M4 MoE tuned-config folder is absent from server environment\\n'\'' >&2"
    print "  exit 1"
    print "}"
    print "config_file='\''/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m4/E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json'\''"
    print "[[ \"$(sha256sum \"$config_file\" | cut -d'\'' '\'' -f1)\" == f93b5e1d5863e04268eb96877ab2ef6ba0990c42c62f1dff27bc36676c30bf7f ]] || exit 1"
    print "[[ \"$(jq -r '\''.\"4\".num_warps'\'' \"$config_file\")\" == 8 ]] || exit 1"
    skip_async = 1
    next
  }
  if ($0 == "        \"async_uva_ple_prefetch\": true,") {
    print "        \"async_uva_ple_prefetch\": false,"
    print "        \"moe_m4_num_warps\": 8,"
    print "        \"tuned_config_sha256\": \"f93b5e1d5863e04268eb96877ab2ef6ba0990c42c62f1dff27bc36676c30bf7f\","
    next
  }
  if ($0 == "server_command=$(tr '\''\\0'\'' '\'' '\'' <\"/proc/${server_pid}/cmdline\")") {
    print
    print "grep -Fq '\''Using configuration from /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m4/E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json for MoE layer.'\'' \"${run_dir}/server.log\" || {"
    print "  printf '\''FAIL: live server did not select the frozen M4 MoE config\\n'\'' >&2"
    print "  exit 1"
    print "}"
    next
  }
  print
}
' 
}

[[ $# == 0 ]] || { printf 'FAIL: A27 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A27 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A27_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
