#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8.sh"
rewrite="${script_dir}/rewrite-a30-hybrid-stage-contract.py"
expected_base=6a624362e1ae1d4c4522fbc6cd88c6ac9e7da0da7998390c28333927c3aec5b0
expected_rewrite=b68ce87cdd3403e4a7ac246c6c9580e420a5492ab4c91e42b9ea15ef19d229d4
expected_source=fe815b8419a60ba24bc9a2f21182fc3b780bb40e22885358c2eed53782f21e95
expected_inner=8733a114124632c3fe47edaefac261f57e4999d1af211152f79a0ca8a29758f0

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

derive() {
  Q38_A29_SOURCE_ONLY=1 "$base" | awk -v rewrite="$rewrite" -v inner="$expected_inner" '
{
  gsub(/ple-only-a29-moe-m1-warps8/, "ple-only-a30-hc-grouped-m1")
  gsub(/q38-mtp0-ple-only-a29/, "q38-mtp0-ple-only-a30")
  gsub(/q38-ple-only-a29/, "q38-ple-only-a30")
  gsub(/q38-ple4k-a29/, "q38-ple4k-a30")
  gsub(/attempt29/, "attempt30")
  gsub(/ATTEMPT=29 PORT=19701/, "ATTEMPT=30 PORT=19702")
  gsub(/19701/, "19702")
  gsub(/Q38_A29_VALIDATE_ONLY/, "Q38_A30_VALIDATE_ONLY")
  gsub(/A29/, "A30")
  gsub(/moe-m1-warps8-selected-trace-off/, "moe-m1-warps8-hc-grouped-up-trace-off")
  gsub(/d14396e27247c1b251da0ce24a0942772c4b002f/, "797769b34b6db5c934609b75dc04cc61ec66e5f9")
  gsub(/\/mnt\/usb-models\/qwen38-build\/runtime-core-moe-negidguard-b70/, "/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2")
  if ($0 == "expected_derived=37791a9b20d0ce0d10e89f3930f9d0e8b7d7f743e1074691b39ed22a40e6adbb") {
    print "expected_derived=" inner
    next
  }
  if ($0 == "\"/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/rewrite-a29-kernel-workspace-contract.py\" \"$derived\"") {
    print "\"" rewrite "\" \"$derived\""
    next
  }
  if ($0 == "export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1") {
    print
    print "export VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP=1"
    next
  }
  if ($0 == "if [[ \"${Q38_A30_VALIDATE_ONLY:-0}\" == 1 ]]; then") {
    print "if [[ \"${Q38_A30_INNER_SOURCE_ONLY:-0}\" == 1 ]]; then cat \"$derived\"; exit 0; fi"
    print
    next
  }
  print
}
'
}

[[ $# == 0 ]] || fail "A30 launcher takes no arguments"
[[ -f "$base" && ! -L "$base" ]] || fail "A29 launcher is absent or not regular"
[[ -f "$rewrite" && ! -L "$rewrite" ]] || fail "A30 rewrite helper is absent or not regular"
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || fail "A29 launcher drifted"
[[ "$(sha256sum "$rewrite" | cut -d' ' -f1)" == "$expected_rewrite" ]] || fail "A30 rewrite helper drifted"
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || fail "derived A30 outer launcher $actual_source is not frozen $expected_source"
if [[ "${Q38_A30_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi

if [[ "${Q38_A30_VALIDATE_ONLY:-0}" != 1 && "${Q38_A30_INNER_SOURCE_ONLY:-0}" != 1 ]]; then
  stage=/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2
  stage_manifest="${stage}-evidence/runtime-stage.sha256"
  finalizer_manifest="${stage}-evidence/finalizer-evidence.sha256"
  qualification_manifest=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/grouped-serving-stage-eeee7d6-a2-qualification-a4/qualification-evidence.sha256
  run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt30
  cache_dir=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt30
  [[ "$(git -C /home/steve/src/vllm-current-main rev-parse HEAD)" == 797769b34b6db5c934609b75dc04cc61ec66e5f9 ]] || fail "vLLM head changed before boot claim"
  [[ -z "$(git -C /home/steve/src/vllm-current-main status --porcelain)" ]] || fail "vLLM source is dirty before boot claim"
  [[ "$(git -C /home/steve/src/vllm-xpu-kernels rev-parse HEAD)" == eeee7d671abfa964626baa18da2174bb92cac80a ]] || fail "kernel head changed before boot claim"
  [[ "$(git -C /home/steve/src/vllm-xpu-kernels rev-list --max-count=5 HEAD)" == $'eeee7d671abfa964626baa18da2174bb92cac80a\n042c6e877b667f03087091ce3ab58b80903afc20\na6ee94fd8fadb97dc033921f1019ef18f14d5dd0\n359466a262489bdf4e1774e3572202dc82a00718\nad25aa9f69a2171612b9c6b83dfa82c69559f9e4' ]] || fail "kernel chain changed before boot claim"
  [[ -z "$(git -C /home/steve/src/vllm-xpu-kernels status --porcelain --untracked-files=no)" ]] || fail "kernel source is dirty before boot claim"
  [[ "$(git -C /home/steve/src/vllm-xpu-kernels status --porcelain)" == '?? third_party/' ]] || fail "kernel untracked state changed before boot claim"
  [[ "$(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/fast-ai)" == '/dev/nvme0n1p2 ext4 /' ]] || fail "hybrid stage is not on authenticated NVMe"
  [[ "$(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)" == '/dev/sda2 fuseblk /mnt/usb-models' ]] || fail "evidence drive is not authenticated"
  [[ "$(sha256sum "$stage_manifest" | cut -d' ' -f1)" == a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d ]] || fail "hybrid stage manifest changed before boot claim"
  [[ "$(sha256sum "$finalizer_manifest" | cut -d' ' -f1)" == 2c049273bfc9e8dd429e2f74969cb9c4917a6e23833fcb8e8584ba8944a62aee ]] || fail "hybrid finalizer evidence changed before boot claim"
  [[ "$(sha256sum "$qualification_manifest" | cut -d' ' -f1)" == ca218488129510e0bc29175f96fd17f0572ecbc2e0f7913ce3c576d25b5b3591 ]] || fail "A4 evidence changed before boot claim"
  (cd "$stage/vllm_xpu_kernels" && sha256sum -c "$stage_manifest") >/dev/null || fail "hybrid stage closure failed before boot claim"
  (cd /home/steve/llm-optimizations && sha256sum -c "$finalizer_manifest") >/dev/null || fail "finalizer closure failed before boot claim"
  sha256sum -c "$qualification_manifest" >/dev/null || fail "A4 closure failed before boot claim"
  [[ "$(sha256sum /home/steve/src/vllm-current-main/vllm/models/qwen4_exp/amd/low_latency_gemm.py | cut -d' ' -f1)" == 5d9f99945f2f01396afdece710e69b719139bf57fb2232cb831b467b8f64737f ]] || fail "HC grouped source changed before boot claim"
  [[ "$(sha256sum /home/steve/src/vllm-current-main/vllm/envs.py | cut -d' ' -f1)" == 5dda238b194947d046169c9a0f9bead7f30c420b6943cdd8d1b15291dfa99906 ]] || fail "HC environment source changed before boot claim"
  [[ "$(sha256sum /home/steve/llm-optimizations/patches/qwen38-flash-next-fp8-b70/vllm/0033-Qualify-Qwen-HC-grouped-up-dynamic-shapes.patch | cut -d' ' -f1)" == 1944280fa2f3debf684d1ade665b8d40237edf866fc0415bb53f43b1f1ea71bb ]] || fail "HC grouped patch snapshot changed before boot claim"
  [[ ! -e "$run_dir" && ! -e "$cache_dir" ]] || fail "A30 run or cache path already exists"
fi
source <(derive)
