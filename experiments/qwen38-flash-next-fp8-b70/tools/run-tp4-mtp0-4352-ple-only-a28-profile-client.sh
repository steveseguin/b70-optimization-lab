#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a26-async-uva-client.sh"
profile_helper="${script_dir}/run-q38-a28-profile-window.sh"
expected_base=3c5ebbf7182fe6bfb8c516f2f75e83d749dc98d18b9c3885330b4e9024e5e7d0
expected_profile_helper=17e5bd6957ce4e94931d06b43fdac3ca5c7906ee410d3080382eda4a5bb025ba
expected_source=fd995221b5e30fe375b70e76ca53c6f35a015a44bd64b654c3cdf65abf0f1769

derive() {
  Q38_A26_SOURCE_ONLY=1 "$base" | awk '
BEGIN { skip_async = 0; injected = 0 }
skip_async { if ($0 == "}") skip_async = 0; next }
{
  gsub(/ple-only-a26-async-uva/, "ple-only-a28-profile")
  gsub(/q38-mtp0-ple-only-a26/, "q38-mtp0-ple-only-a28")
  gsub(/q38-ple-only-a26/, "q38-ple-only-a28")
  gsub(/attempt26/, "attempt28")
  gsub(/19698/, "19700")
  gsub(/async-uva-ple-trace-off/, "target-step-xpu-profile")
  if (index($0, "grep -zFxq '\''VLLM_XPU_PLE_UVA_PREFETCH=1'\''") == 1) {
    print "if grep -zFq '\''VLLM_XPU_PLE_UVA_PREFETCH='\'' \"/proc/${server_pid}/environ\"; then"
    print "  printf '\''FAIL: async UVA PLE selector unexpectedly present in server environment\\n'\'' >&2"
    print "  exit 1"
    print "fi"
    print "if grep -zFq '\''VLLM_TUNED_CONFIG_FOLDER='\'' \"/proc/${server_pid}/environ\"; then"
    print "  printf '\''FAIL: tuned MoE folder unexpectedly present in server environment\\n'\'' >&2"
    print "  exit 1"
    print "fi"
    skip_async = 1
    next
  }
  if ($0 == "[[ \"$server_command\" != *\"--speculative-config\"* && \"$server_command\" != *\"--reasoning-parser\"* ]] || {") {
    print "[[ \"$server_command\" == *\"--profiler-config\"* && \"$server_command\" == *'\''\"delay_iterations\":65'\''* && \"$server_command\" == *'\''\"max_iterations\":4'\''* && \"$server_command\" == *'\''\"torch_profiler_record_shapes\":true'\''* ]] || {"
    print "  printf '\''FAIL: frozen A28 profiler config is absent from server command\\n'\'' >&2"
    print "  exit 1"
    print "}"
    print ""
    print ""
  }
  if ($0 == "set +e" && injected == 0) {
    print "[[ \"$(sha256sum /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/run-q38-a28-profile-window.sh | cut -d'\'' '\'' -f1)\" == 17e5bd6957ce4e94931d06b43fdac3ca5c7906ee410d3080382eda4a5bb025ba ]] || exit 1"
    print "/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/run-q38-a28-profile-window.sh"
    print ""
    injected = 1
  }
  if ($0 == "        \"async_uva_ple_prefetch\": true,") {
    print "        \"async_uva_ple_prefetch\": False,"
    print "        \"profiler\": \"torch_xpu_report_only\","
    print "        \"profile_delay_iterations\": 65,"
    print "        \"profile_max_iterations\": 4,"
    next
  }
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A28 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$profile_helper" | cut -d' ' -f1)" == "$expected_profile_helper" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A28 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A28_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
