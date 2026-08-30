#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a21-external-trace.sh"
expected_base=e60da9b46f31f43224d0564d519b801ee99ee133c042cacb4af1442da9bc18c5
expected_source=b32a64b4444639b113c625e38597c5390c200844ac304fdb2a4f7ebb84541646

derive() {
  Q38_A21_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a21/, "ple-only-a22")
  gsub(/q38-ple4k-a21/, "q38-ple4k-a22")
  gsub(/attempt21/, "attempt22")
  gsub(/ATTEMPT=21 PORT=19693/, "ATTEMPT=22 PORT=19694")
  gsub(/19693/, "19694")
  gsub(/Q38_A21_VALIDATE_ONLY/, "Q38_A22_VALIDATE_ONLY")
  gsub(/9f720cd4aa6c8a8b045f54dfa10f5b8611caccbd/, "613afcc501331aa6ff7d5a238a6c9a5d45777b3e")
  if (index($0, "export Q38_REPEATABILITY_TRACE_FILE=") == 1) {
    print
    print "export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK=all"
    next
  }
  if ($0 == "expected_derived=457cf9cd35de77abc1c51f07702555625a148c19ae7204d27d7bc313bb282a4a")
    print "expected_derived=3119e7a55d95050ae3188582d6510cba7c70673876cf3981f8cfa76302dbaafa"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A22 inner-trace launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A22 source %s\n' "$actual_source" >&2; exit 1; }
if [[ "${Q38_A22_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
if [[ "${Q38_A22_VALIDATE_ONLY:-0}" != 1 ]]; then
  boot_id=$(< /proc/sys/kernel/random/boot_id)
  forbidden_boot_id=cd0bdf29-81e9-46e0-a48e-3504dee1c625
  [[ "$boot_id" != "$forbidden_boot_id" ]] || {
    printf 'FAIL: A22 is forbidden in the post-A21 boot %s\n' "$boot_id" >&2
    exit 1
  }
  full_load_marker="/run/user/$(id -u)/q38-flash-next-full-load.boot-id"
  if [[ -e "$full_load_marker" ]] && [[ "$(< "$full_load_marker")" == "$boot_id" ]]; then
    printf 'FAIL: a Qwen3.8 Flash-Next full-load attempt is already marked in boot %s\n' "$boot_id" >&2
    exit 1
  fi
  marker_tmp="${full_load_marker}.tmp.$$"
  printf '%s\n' "$boot_id" >"$marker_tmp"
  mv "$marker_tmp" "$full_load_marker"
fi
source <(derive)
