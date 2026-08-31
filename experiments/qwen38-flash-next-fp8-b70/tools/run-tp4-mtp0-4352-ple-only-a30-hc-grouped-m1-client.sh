#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8-client.sh"
expected_base=28e89555634fe22a06cf87d8bc15fbb69fe6230981ddaef34d9a7fe1476b6981
expected_source=116ddf13fff1a556565b98484ebcb78724d30d56ad9a82d9fcebbf72dbcdd703

derive() {
  Q38_A29_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a29-moe-m1-warps8/, "ple-only-a30-hc-grouped-m1")
  gsub(/q38-mtp0-ple-only-a29/, "q38-mtp0-ple-only-a30")
  gsub(/q38-ple-only-a29/, "q38-ple-only-a30")
  gsub(/attempt29/, "attempt30")
  gsub(/19701/, "19702")
  gsub(/moe-m1-warps8-selected-trace-off/, "moe-m1-warps8-hc-grouped-up-trace-off")
  gsub(/d14396e27247c1b251da0ce24a0942772c4b002f/, "797769b34b6db5c934609b75dc04cc61ec66e5f9")
  gsub(/ad25aa9f69a2171612b9c6b83dfa82c69559f9e4/, "eeee7d671abfa964626baa18da2174bb92cac80a")
  gsub(/2f829747503c77d4814834dffd0840fb1dd9f75a/, "eeee7d671abfa964626baa18da2174bb92cac80a")
  gsub(/\/mnt\/usb-models\/qwen38-build\/runtime-core-moe-negidguard-b70/, "/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2")
  if ($0 == "config_file='\''/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1/E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json'\''") {
    print "grep -zFxq '\''VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP=1'\'' \"/proc/${server_pid}/environ\" || { printf '\''FAIL: grouped-HC selector is absent from server environment\\n'\'' >&2; exit 1; }"
    print "[[ \"$(sha256sum /home/steve/src/vllm-current-main/vllm/models/qwen4_exp/amd/low_latency_gemm.py | cut -d'\'' '\'' -f1)\" == 5d9f99945f2f01396afdece710e69b719139bf57fb2232cb831b467b8f64737f ]] || exit 1"
    print "[[ \"$(sha256sum /home/steve/src/vllm-current-main/vllm/envs.py | cut -d'\'' '\'' -f1)\" == 5dda238b194947d046169c9a0f9bead7f30c420b6943cdd8d1b15291dfa99906 ]] || exit 1"
    print "[[ \"$(git -C /home/steve/src/vllm-xpu-kernels rev-parse HEAD)\" == eeee7d671abfa964626baa18da2174bb92cac80a ]] || exit 1"
    print "[[ \"$(git -C /home/steve/src/vllm-xpu-kernels rev-list --max-count=5 HEAD)\" == $'\''eeee7d671abfa964626baa18da2174bb92cac80a\\n042c6e877b667f03087091ce3ab58b80903afc20\\na6ee94fd8fadb97dc033921f1019ef18f14d5dd0\\n359466a262489bdf4e1774e3572202dc82a00718\\nad25aa9f69a2171612b9c6b83dfa82c69559f9e4'\'' ]] || exit 1"
    print
    next
  }
  if ($0 == "  '\''runtime_stage_build_head=eeee7d671abfa964626baa18da2174bb92cac80a'\'' \\") {
    print "  '\''runtime_stage_native_head=eeee7d671abfa964626baa18da2174bb92cac80a'\'' " sprintf("%c", 92)
    print "  '\''runtime_stage_retained_base_head=2f829747503c77d4814834dffd0840fb1dd9f75a'\'' " sprintf("%c", 92)
    print "  '\''runtime_stage_manifest_sha256=a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d'\'' " sprintf("%c", 92)
    print "  '\''runtime_stage_qualification_sha256=ca218488129510e0bc29175f96fd17f0572ecbc2e0f7913ce3c576d25b5b3591'\'' " sprintf("%c", 92)
    print "  '\''hc_grouped_up=1'\'' " sprintf("%c", 92)
    next
  }
  if ($0 == "        \"stage_build_head\": \"eeee7d671abfa964626baa18da2174bb92cac80a\",") {
    print "        \"stage_native_head\": \"eeee7d671abfa964626baa18da2174bb92cac80a\","
    print "        \"stage_retained_base_head\": \"2f829747503c77d4814834dffd0840fb1dd9f75a\","
    print "        \"stage_manifest_sha256\": \"a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d\","
    print "        \"stage_qualification_sha256\": \"ca218488129510e0bc29175f96fd17f0572ecbc2e0f7913ce3c576d25b5b3591\","
    print "        \"hc_grouped_up\": True,"
    next
  }
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A30 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || exit 1
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A30 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A30_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
