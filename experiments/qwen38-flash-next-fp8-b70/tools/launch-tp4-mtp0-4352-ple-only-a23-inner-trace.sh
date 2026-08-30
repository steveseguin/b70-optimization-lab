#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a22-inner-trace.sh"
expected_base=18889ab0e8a8602bd02a22f775a903eafcc9ac4d2bd01db2ac0f102a9edc3c60
expected_source=8b8b9166f54d89808d7b7b6d9708ede0e61c0e88dd2cfa75edca7834bbc14eee

derive() {
  Q38_A22_SOURCE_ONLY=1 "$base" | awk '
{
  if ($0 == "  gsub(/12\\.25/, \"12.0\")")
    print "  gsub(/diagnostics=none/, \"diagnostics=qwen4exp-ple-inner-trace-rank-all\")"
  if (index($0, "grep -Fxq '\''expected_vllm_head=") == 1) {
    gsub(/613afcc501331aa6ff7d5a238a6c9a5d45777b3e/, "f69a0ef46338f93636671c87caa527b3ac2ca129")
    print
    print "grep -Fxq \"  printf '\''diagnostics=qwen4exp-ple-inner-trace-rank-all\\n'\''\" \"$derived\""
    print "! grep -Fq \"diagnostics=none\" \"$derived\""
    next
  }
  gsub(/ple-only-a22/, "ple-only-a23")
  gsub(/q38-ple4k-a22/, "q38-ple4k-a23")
  gsub(/attempt22/, "attempt23")
  gsub(/ATTEMPT=22 PORT=19694/, "ATTEMPT=23 PORT=19695")
  gsub(/19694/, "19695")
  gsub(/Q38_A22_VALIDATE_ONLY/, "Q38_A23_VALIDATE_ONLY")
  gsub(/613afcc501331aa6ff7d5a238a6c9a5d45777b3e/, "f69a0ef46338f93636671c87caa527b3ac2ca129")
  if ($0 == "expected_derived=3119e7a55d95050ae3188582d6510cba7c70673876cf3981f8cfa76302dbaafa")
    print "expected_derived=7ffd700cce21da36173ea795366a01de845694c0b61781f7a421a808dd19df91"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A23 inner-trace launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A23 source %s\n' "$actual_source" >&2; exit 1; }
if [[ "${Q38_A23_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
if [[ "${Q38_A23_VALIDATE_ONLY:-0}" != 1 ]]; then
  boot_id=$(< /proc/sys/kernel/random/boot_id)
  forbidden_boot_id=c9c86120-4735-4f7a-9500-d7e49f0d2f63
  [[ "$boot_id" != "$forbidden_boot_id" ]] || {
    printf 'FAIL: A23 is forbidden in the consumed A22 boot %s\n' "$boot_id" >&2
    exit 1
  }
  full_load_marker="/run/user/$(id -u)/q38-flash-next-full-load.boot-id"
  full_load_lock="${full_load_marker}.lock"
  exec 9>"$full_load_lock"
  flock -n 9 || {
    printf 'FAIL: another Qwen3.8 Flash-Next launch is claiming this boot\n' >&2
    exit 1
  }
  if [[ -e "$full_load_marker" ]] && [[ "$(< "$full_load_marker")" == "$boot_id" ]]; then
    printf 'FAIL: a Qwen3.8 Flash-Next full-load attempt is already marked in boot %s\n' "$boot_id" >&2
    exit 1
  fi
  marker_tmp="${full_load_marker}.tmp.$$"
  printf '%s\n' "$boot_id" >"$marker_tmp"
  mv "$marker_tmp" "$full_load_marker"
  flock -u 9
  exec 9>&-
fi
source <(derive)
