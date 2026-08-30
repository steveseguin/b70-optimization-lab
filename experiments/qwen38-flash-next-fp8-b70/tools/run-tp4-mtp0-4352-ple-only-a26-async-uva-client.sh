#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a25-local-inner-trace-client.sh"
expected_base=be4cd1d7f15669a71061e3a7567d796431bc37a624f9026e12eb3418a5818f65
expected_source=d5c0b6c2ffd1a7688f258fb748a182af70f39dc2e46a80c6cf027c18db6097d8

derive() {
  Q38_A25_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a25-local-inner-trace/, "ple-only-a26-async-uva")
  gsub(/q38-mtp0-ple-only-a25/, "q38-mtp0-ple-only-a26")
  gsub(/q38-ple-only-a25/, "q38-ple-only-a26")
  gsub(/attempt25/, "attempt26")
  gsub(/19697/, "19698")
  gsub(/ca20c4465ca34fc733aac70416b75d7cb8a1c46f/, "d14396e27247c1b251da0ce24a0942772c4b002f")
  gsub(/diagnostics=qwen4exp-ple-inner-trace-rank-all/, "diagnostics=async-uva-ple-trace-off")
  gsub(/"diagnostics": "qwen4exp-ple-inner-trace-rank-all"/, "\"diagnostics\": \"async-uva-ple-trace-off\"")
  if ($0 == "server_command=$(tr '\''\\0'\'' '\'' '\'' <\"/proc/${server_pid}/cmdline\")") {
    print
    print "grep -zFxq '\''VLLM_XPU_PLE_UVA_PREFETCH=1'\'' \"/proc/${server_pid}/environ\" || {"
    print "  printf '\''FAIL: async UVA PLE selector is absent from server environment\\n'\'' >&2"
    print "  exit 1"
    print "}"
    print "grep -zFxq '\''PYTHONPATH=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70:/home/steve/src/vllm-current-main'\'' \"/proc/${server_pid}/environ\" || {"
    print "  printf '\''FAIL: live server PYTHONPATH identity mismatch\\n'\'' >&2"
    print "  exit 1"
    print "}"
    print "if grep -zEq '\''^(Q38_REPEATABILITY_TRACE_FILE|VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_FILE|VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK)='\'' \"/proc/${server_pid}/environ\"; then"
    print "  printf '\''FAIL: trace selector unexpectedly present in live server environment\\n'\'' >&2"
    print "  exit 1"
    print "fi"
    print "[[ \"$(git -C /home/steve/src/vllm-current-main rev-parse HEAD)\" == d14396e27247c1b251da0ce24a0942772c4b002f ]] || {"
    print "  printf '\''FAIL: live vLLM checkout head changed\\n'\'' >&2"
    print "  exit 1"
    print "}"
    print "[[ -z \"$(git -C /home/steve/src/vllm-current-main status --porcelain)\" ]] || {"
    print "  printf '\''FAIL: live vLLM checkout is dirty\\n'\'' >&2"
    print "  exit 1"
    print "}"
    next
  }
  if ($0 == "        \"placement\": \"ple_only_uva\", \"ple_host_bytes_per_rank\": 12800061440,") {
    print
    print "        \"async_uva_ple_prefetch\": true,"
    next
  }
  print
}
' 
}

[[ $# == 0 ]] || { printf 'FAIL: A26 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A26 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A26_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
