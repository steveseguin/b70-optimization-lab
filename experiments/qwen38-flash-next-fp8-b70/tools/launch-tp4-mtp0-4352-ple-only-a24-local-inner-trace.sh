#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a23-inner-trace.sh"
expected_base=9194d3065d2c6ad1fd0e86e6054d0dd398f3d2510f098090c0c06562bfe04874
expected_source=bbfe3122d059c163aa6d03317b364f69059cde95e75cb666e29f0e27c01174af

derive() {
  Q38_A23_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a23/, "ple-only-a24")
  gsub(/q38-ple4k-a23/, "q38-ple4k-a24")
  gsub(/attempt23/, "attempt24")
  gsub(/ATTEMPT=23 PORT=19695/, "ATTEMPT=24 PORT=19696")
  gsub(/19695/, "19696")
  gsub(/Q38_A23_VALIDATE_ONLY/, "Q38_A24_VALIDATE_ONLY")
  gsub(/\/mnt\/usb-models\/llm-models\/Qwen3.8-Flash-Next-FP8/, "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8")
  if ($0 == "expected_derived=7ffd700cce21da36173ea795366a01de845694c0b61781f7a421a808dd19df91")
    print "expected_derived=eaa798bbe327bc1aea749cf8c47e9246c410637ea7bfef7a740350eca0100a30"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A24 local inner-trace launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A24 source %s\n' "$actual_source" >&2; exit 1; }
if [[ "${Q38_A24_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
if [[ "${Q38_A24_VALIDATE_ONLY:-0}" != 1 ]]; then
  boot_id=$(< /proc/sys/kernel/random/boot_id)
  required_boot_id=c9c86120-4735-4f7a-9500-d7e49f0d2f63
  [[ "$boot_id" == "$required_boot_id" ]] || {
    printf 'FAIL: A24 authorization is frozen to boot %s, not %s\n' "$required_boot_id" "$boot_id" >&2
    exit 1
  }
  general_marker="/run/user/$(id -u)/q38-flash-next-full-load.boot-id"
  [[ -e "$general_marker" ]] && [[ "$(< "$general_marker")" == "$boot_id" ]] || {
    printf 'FAIL: A24 requires the recorded A22 load in boot %s\n' "$boot_id" >&2
    exit 1
  }
  mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
  swap_free_kib=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
  nvme_available_bytes=$(df -B1 --output=avail /mnt/fast-ai | tail -1 | tr -d ' ')
  (( mem_available_kib >= 120000000 )) || { printf 'FAIL: A24 requires MemAvailable >= 120000000 KiB\n' >&2; exit 1; }
  (( swap_free_kib >= 8000000 )) || { printf 'FAIL: A24 requires SwapFree >= 8000000 KiB\n' >&2; exit 1; }
  (( nvme_available_bytes >= 220000000000 )) || { printf 'FAIL: A24 requires >= 220000000000 free NVMe bytes\n' >&2; exit 1; }
  attempt_marker="/run/user/$(id -u)/q38-flash-next-a24-local-second-load.boot-id"
  attempt_lock="${attempt_marker}.lock"
  exec 9>"$attempt_lock"
  flock -n 9 || { printf 'FAIL: A24 launch claim is busy\n' >&2; exit 1; }
  [[ ! -e "$attempt_marker" ]] || { printf 'FAIL: A24 was already attempted\n' >&2; exit 1; }
  marker_tmp="${attempt_marker}.tmp.$$"
  printf '%s\n' "$boot_id" >"$marker_tmp"
  mv "$marker_tmp" "$attempt_marker"
  flock -u 9
  exec 9>&-
fi
source <(derive)
