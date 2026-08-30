#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a16-trace.sh"
expected_base=a4d93efb63511c5a7340b45b522b2f07b675b45d40c455601deae79768f5cffc
expected_source=10311a780e27b5edc35ba5760fa2b2b30cc388603c47c16b28831ba9e0f430f0

derive() {
  Q38_A16_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a16/, "ple-only-a17")
  gsub(/attempt16/, "attempt17")
  gsub(/19688/, "19689")
  gsub(/0b5482ab292bf8f054fab026ad9a3c9eef9ef4a7522c17a74a16677b317f7f2b/, "083b0af6b0632ab547cc86553bec19104386fae1cb73da791baf9957ecfeddc0")
  gsub(/171816212130fdc0453bf27f576015c88575c45ff87da8543f6cbe0608a6a4ac/, "3d52f02efe0794a76ed1eb12311299126612b86dc3cbd3062df1d8fcdd0ba7c9")
  gsub(/Q38_A16_VALIDATE_ONLY/, "Q38_A17_VALIDATE_ONLY")
  if ($0 == "expected_derived=e0e0582e90be05e8c5336510a3d2601d328c52870a87f2d9f9d54bc2f119ca77")
    print "expected_derived=f8c8be8a9d6cf2fb82658cf100018743ff001ae26462125482787d855b476662"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A17 trace supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A17 trace supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A17_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
