#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-q38-hc-silu-a1.sh"
a1_gate="${script_dir}/benchmark-q38-hc-silu-a1.py"
a1_patch=/home/steve/llm-optimizations/patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0009-Add-exact-Qwen4Exp-HC-SiLU-XPU-kernel.patch
expected_base=8ea486f429ca6845941a80cd610ba7a8305f7ac44b0d6091f52d2778d39eac56
expected_a1_gate=a254a5567ca8251dac49c060a15b73ced16132a712045c09ccc36a12418efb71
expected_a1_patch=12e5c31dea78ffeba4aadc209a78ae06e0a3d6b9f4f04ef497734f148264e3fb
expected_source=dad3a3988b0a9a3d8f15c88537480242e34c3f960749844aa24e35781024dbd6
expected_self=ee08478250dbd6b1231eb4572f69d0632dd56b9906fe8bbd1855df2748a6f74e

derive() {
  awk '
BEGIN {
  skip_canonical = 0
  skip_cleanup_handler = 0
  skip_full_load_guard = 0
  skip_runtime_cleanup = 0
  skip_runtime_postflight = 0
  skip_prior_component_guard = 0
  skip_component_claim = 0
  skip_component_completion = 0
}
{
  if (skip_canonical > 0) {
    skip_canonical--
    next
  }
  if (skip_cleanup_handler) {
    if ($0 == "trap '\''exit 143'\'' TERM") {
      skip_cleanup_handler = 0
      print "trap finalize_lifecycle EXIT"
      print "trap '\''exit 130'\'' INT"
      print "trap '\''exit 143'\'' TERM HUP"
    }
    next
  }
  if (skip_runtime_cleanup) {
    if ($0 == "cleanup_armed=0")
      skip_runtime_cleanup = 0
    next
  }
  if (skip_runtime_postflight) {
    if (index($0, "sha256sum -c evidence.sha256") > 0)
      skip_runtime_postflight = 0
    next
  }
  if (skip_full_load_guard) {
    if ($0 == "exec 10>\"$component_state_lock\"") {
      skip_full_load_guard = 0
      skip_component_claim = 1
    }
    next
  }
  if (skip_prior_component_guard) {
    if ($0 == "fi")
      skip_prior_component_guard = 0
    next
  }
  if (skip_component_claim) {
    if ($0 == "component_claimed=1")
      skip_component_claim = 0
    next
  }
  if (skip_component_completion) {
    if ($0 == "mv -f -- \"$state_tmp\" \"$component_state\"")
      skip_component_completion = 0
    next
  }
  gsub(/benchmark-q38-hc-silu-a1.py/, "benchmark-q38-hc-silu-a2-stdexp.py")
  gsub(/runtime-q38-hc-silu-a1/, "runtime-q38-hc-silu-a2-stdexp")
  gsub(/20260831-q38-hc-silu-a1/, "20260831-q38-hc-silu-a2-stdexp")
  gsub(/Q38_HC_SILU_A1_VALIDATE_ONLY/, "Q38_HC_SILU_A2_VALIDATE_ONLY")
  gsub(/Q38_RUN_HC_SILU_A1/, "Q38_RUN_HC_SILU_A2")
  gsub(/VALID: q38-hc-silu-a1/, "VALID: q38-hc-silu-a2-stdexp")
  gsub(/the prior event-chain failure boot is ineligible/, "the A1 component-attempt boot is ineligible")
  gsub(/Serialize against full-model work and any other GPU0 component before making/, "Serialize against model work and any other GPU0 component before starting")
  gsub(/the boot-consuming claim. These descriptors remain held for the entire run./, "the device action. These descriptors remain held for the entire run.")
  if ($0 == "kernel_patch=\"${repo}/patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0009-Add-exact-Qwen4Exp-HC-SiLU-XPU-kernel.patch\"") {
    print "kernel_patch=\"${repo}/patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0010-Match-installed-Torch-HC-SiLU-exp-arithmetic.patch\""
    next
  }
  if ($0 ~ /^rejected_boot=/ || $0 ~ /^full_load_marker=/ || $0 ~ /^component_state/ || $0 == "component_claimed=0")
    next
  if (index($0, "[[ \"$boot\" != \"$rejected_boot\" ]]") > 0)
    next
  if ($0 == "exec 9>\"${full_load_marker}.lock\"") {
    skip_full_load_guard = 1
    next
  }
  if ($0 == "if [[ -e \"$component_state\" ]]; then") {
    skip_prior_component_guard = 1
    next
  }
  if ($0 == "exec 10>\"$component_state_lock\"") {
    skip_component_claim = 1
    next
  }
  if (index($0, "[[ \"$component_claimed\" == 1 ]]") > 0) {
    skip_component_completion = 1
    next
  }
  if ($0 ~ /^loader=/) {
    print
    print "lifecycle_started=1"
    print "timeout --signal=TERM --kill-after=10s 90s env -i \\"
    print "  HOME=/home/steve \\"
    print "  PATH=\"${cmplr}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\" \\"
    print "  LD_LIBRARY_PATH=\"$loader\" \\"
    print "  OCL_ICD_FILENAMES=\"${cmplr}/lib/libintelocl.so\" \\"
    print "  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \\"
    print "  ZE_AFFINITY_MASK=0,1,2,3 \\"
    print "  \"$python\" \"$postflight\" --output \"$output/four-b70-preflight.json\" \\"
    print "  >\"$output/four-b70-preflight.log\" 2>&1 || fail \"bounded four-B70 preflight failed\""
    next
  }
  if ($0 == "cleanup_on_exit() {") {
    print "lifecycle_started=0"
    print "lifecycle_finished=0"
    print "finalize_lifecycle() {"
    print "  local incoming_rc=$? final_rc cleanup_status postflight_status"
    print "  local mem_available_kib swap_free_kib"
    print "  final_rc=$incoming_rc"
    print "  cleanup_status=passed"
    print "  postflight_status=passed"
    print "  trap - EXIT"
    print "  trap '\'''\'' INT TERM HUP"
    print "  if [[ \"$lifecycle_started\" == 1 && \"$lifecycle_finished\" == 0 ]]; then"
    print "    set +e"
    print "    if [[ -n \"$(component_pids)\" ]]; then"
    print "      cleanup_status=required"
    print "      cleanup_component"
    print "    fi"
    print "    if [[ -n \"$(component_pids)\" ]]; then"
    print "      cleanup_status=failed"
    print "    fi"
    print "    if ! timeout 30s xpu-smi discovery -j >\"$output/discovery-after.json\" 2>\"$output/discovery-after.err\"; then"
    print "      postflight_status=discovery-failed"
    print "    elif ! jq -e '\''.device_list | map(.pci_bdf_address) == [\"0000:23:00.0\", \"0000:27:00.0\", \"0000:43:00.0\", \"0000:47:00.0\"]'\'' \"$output/discovery-after.json\" >/dev/null; then"
    print "      postflight_status=topology-failed"
    print "    fi"
    print "    if ! timeout --signal=TERM --kill-after=10s 90s env -i \\"
    print "      HOME=/home/steve \\"
    print "      PATH=\"${cmplr}/bin:${venv}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\" \\"
    print "      LD_LIBRARY_PATH=\"$loader\" \\"
    print "      OCL_ICD_FILENAMES=\"${cmplr}/lib/libintelocl.so\" \\"
    print "      PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \\"
    print "      ZE_AFFINITY_MASK=0,1,2,3 \\"
    print "      \"$python\" \"$postflight\" --output \"$output/four-b70-postflight.json\" \\"
    print "      >\"$output/four-b70-postflight.log\" 2>&1; then"
    print "      postflight_status=\"${postflight_status};four-card-failed\""
    print "    fi"
    print "    awk '\''/MemAvailable|SwapFree/ {print}'\'' /proc/meminfo >\"$output/memory-after.txt\""
    print "    mem_available_kib=$(awk '\''/MemAvailable/ {print $2}'\'' /proc/meminfo)"
    print "    swap_free_kib=$(awk '\''/SwapFree/ {print $2}'\'' /proc/meminfo)"
    print "    [[ \"$mem_available_kib\" -ge 110000000 ]] || postflight_status=\"${postflight_status};memory-failed\""
    print "    [[ \"$swap_free_kib\" -ge 8000000 ]] || postflight_status=\"${postflight_status};swap-failed\""
    print "    if timeout 15s journalctl -b -k --after-cursor \"$journal_cursor\" --no-pager >\"$output/journal-window.txt\" 2>\"$output/journal-window.err\"; then"
    print "      rg -i '\''(xe|i915|drm).*(reset|fault|timed out|timeout|wedg|hang|error)|guc.*(reset|fault|timed out|timeout|wedg|hang|error)|device.*(lost|reset)|cat[_ ]error|page fault|gpu hang'\'' \"$output/journal-window.txt\" >\"$output/journal-fault-matches.txt\" || true"
    print "      [[ ! -s \"$output/journal-fault-matches.txt\" ]] || postflight_status=\"${postflight_status};journal-fault\""
    print "    else"
    print "      : >\"$output/journal-fault-matches.txt\""
    print "      postflight_status=\"${postflight_status};journal-capture-failed\""
    print "    fi"
    print "    if [[ \"$cleanup_status\" != passed || \"$postflight_status\" != passed ]]; then"
    print "      [[ \"$final_rc\" != 0 ]] || final_rc=70"
    print "    fi"
    print "    printf '\''%s\\n'\'' \"$final_rc\" >\"$output/final.rc\""
    print "    jq -n --arg cleanup \"$cleanup_status\" --arg postflight \"$postflight_status\" --argjson incoming_rc \"$incoming_rc\" --argjson final_rc \"$final_rc\" '\''{schema_version:1, cleanup:$cleanup, postflight:$postflight, incoming_rc:$incoming_rc, final_rc:$final_rc}'\'' >\"$output/lifecycle-summary.json\""
    print "    if ! (cd \"$output\" && find . -type f ! -name evidence.sha256 -printf '\''%P\\n'\'' | LC_ALL=C sort | xargs -r sha256sum >evidence.sha256 && sha256sum -c evidence.sha256 >/dev/null); then"
    print "      [[ \"$final_rc\" != 0 ]] || final_rc=70"
    print "      printf '\''%s\\n'\'' \"$final_rc\" >\"$output/final.rc\""
    print "    fi"
    print "    lifecycle_finished=1"
    print "    if [[ \"$final_rc\" == 0 ]]; then printf '\''COMPLETE: %s\\n'\'' \"$output/gate/summary.json\"; fi"
    print "  fi"
    print "  exit \"$final_rc\""
    print "}"
    skip_cleanup_handler = 1
    next
  }
  if ($0 == "if [[ -n \"$(component_pids)\" ]]; then") {
    skip_runtime_cleanup = 1
    next
  }
  if ($0 == "timeout 30s xpu-smi discovery -j >\"$output/discovery-after.json\"") {
    skip_runtime_postflight = 1
    next
  }
  if ($0 == "[[ \"$code\" == 0 ]] || fail \"component failed with exit $code\"") {
    print "[[ \"$code\" == 0 ]] || exit \"$code\""
    next
  }
  if ($0 ~ /^printf '\''COMPLETE:/) {
    print "[[ \"$code\" == 0 ]] || exit \"$code\""
    print "[[ -s \"$output/gate/summary.json\" ]] || fail \"component lacks a complete summary\""
    print "jq -e '\''.status == \"passed\" and .timing.passed == true and .endpoint_authorized == false'\'' \"$output/gate/summary.json\" >/dev/null || fail \"component summary contract failed\""
    print "exit 0"
    next
  }
  if ($0 ~ /^expected_self=/) {
    print "expected_self=2d06fa9c7c8e2a8ed337a52d0c56e3d9c8324a8249309c3a9ad88f369d9388a1"
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
