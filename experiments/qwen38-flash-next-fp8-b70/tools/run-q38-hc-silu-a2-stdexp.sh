#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-q38-hc-silu-a1.sh"
a1_gate="${script_dir}/benchmark-q38-hc-silu-a1.py"
a1_patch=/home/steve/llm-optimizations/patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0009-Add-exact-Qwen4Exp-HC-SiLU-XPU-kernel.patch
expected_base=8ea486f429ca6845941a80cd610ba7a8305f7ac44b0d6091f52d2778d39eac56
expected_a1_gate=a254a5567ca8251dac49c060a15b73ced16132a712045c09ccc36a12418efb71
expected_a1_patch=12e5c31dea78ffeba4aadc209a78ae06e0a3d6b9f4f04ef497734f148264e3fb
expected_source=9fce3860319d668acd6d290126a206fc89f3a582e1b3492ddf79aaaffef57e6e
expected_self=e1317d1d0ad235ba87edb7c5a0f97c8ad47c42afdfc6c74be45bca219de297b7

derive() {
  awk '
BEGIN { skip_canonical = 0 }
{
  if (skip_canonical > 0) {
    skip_canonical--
    next
  }
  gsub(/benchmark-q38-hc-silu-a1.py/, "benchmark-q38-hc-silu-a2-stdexp.py")
  gsub(/runtime-q38-hc-silu-a1/, "runtime-q38-hc-silu-a2-stdexp")
  gsub(/20260831-q38-hc-silu-a1/, "20260831-q38-hc-silu-a2-stdexp")
  gsub(/Q38_HC_SILU_A1_VALIDATE_ONLY/, "Q38_HC_SILU_A2_VALIDATE_ONLY")
  gsub(/Q38_RUN_HC_SILU_A1/, "Q38_RUN_HC_SILU_A2")
  gsub(/VALID: q38-hc-silu-a1/, "VALID: q38-hc-silu-a2-stdexp")
  gsub(/the prior event-chain failure boot is ineligible/, "the A1 component-attempt boot is ineligible")
  if ($0 == "kernel_patch=\"${repo}/patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0009-Add-exact-Qwen4Exp-HC-SiLU-XPU-kernel.patch\"") {
    print "kernel_patch=\"${repo}/patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0010-Match-installed-Torch-HC-SiLU-exp-arithmetic.patch\""
    next
  }
  if ($0 ~ /^rejected_boot=/) {
    print "rejected_boot=a37222ff-628d-4d0a-8a84-37e086ad90dc"
    next
  }
  if ($0 ~ /^expected_self=/) {
    print "expected_self=ab42a0b127d53e6a2b5c162691d8f35e197c8c4f4ccc204572ca0891760769d1"
    next
  }
  if ($0 ~ /^expected_gate=/) {
    print "expected_gate=4f2449f29179eb8fdd1f8642374b460d1d68d61bc1dfcb0d1d050c6f3feed9bb"
    next
  }
  if ($0 ~ /^expected_kernel_patch=/) {
    print "expected_kernel_patch=cf285dddd637c8bd7914002f9d96c3d0c8c23d1cbf8ed34c6413232484d2ca73"
    next
  }
  if ($0 ~ /^expected_dso=/) {
    print "expected_dso=1d7cd1a21c7c2d8ecd0c0b0ef38b549adc133ab12683c0c33eb8d210e5d48e49"
    next
  }
  if ($0 ~ /^expected_manifest=/) {
    print "expected_manifest=be791a78c2c197d60226bc5d74b5773283cd8104b5967ecf1894ef232a7bf002"
    next
  }
  if ($0 == "canonical_self_hash() {") {
    print
    print "  printf \"%s\\\\n\" \"$expected_self\""
    print "}"
    skip_canonical = 2
    next
  }
  print
}
' "$base"
}

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

canonical_self_hash() {
  sed 's/^expected_self=.*/expected_self=SELF_HASH/' "$0" | sha256sum | cut -d' ' -f1
}

[[ $# == 0 ]] || fail "A2 component runner takes no arguments"
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || fail "A1 runner drifted"
[[ "$(sha256sum "$a1_gate" | cut -d' ' -f1)" == "$expected_a1_gate" ]] || fail "A1 gate drifted"
[[ "$(sha256sum "$a1_patch" | cut -d' ' -f1)" == "$expected_a1_patch" ]] || fail "A1 patch drifted"
[[ "$(canonical_self_hash)" == "$expected_self" ]] || fail "A2 wrapper source drifted"
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || fail "A2 derived runner source $actual_source is not frozen $expected_source"
if [[ "${Q38_HC_SILU_A2_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
