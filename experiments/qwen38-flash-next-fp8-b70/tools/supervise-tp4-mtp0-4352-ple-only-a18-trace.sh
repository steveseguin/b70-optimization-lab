#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a17-trace.sh"
expected_base=16bd4f513f50c3fdc429246af95d4df7e1efad683b864ae26c73c691e800e98d
expected_source=5d15f78b3d81d79226f12993fde81f56dbc1d00a0c8721add013f95dac2c5ea7

derive() {
  Q38_A17_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a17/, "ple-only-a18")
  gsub(/attempt17/, "attempt18")
  gsub(/19689/, "19690")
  gsub(/083b0af6b0632ab547cc86553bec19104386fae1cb73da791baf9957ecfeddc0/, "6096391b290369596308e850db622150fc7fc96973d421bbaf8cb19d82046407")
  gsub(/3d52f02efe0794a76ed1eb12311299126612b86dc3cbd3062df1d8fcdd0ba7c9/, "87597d379d9543af956ed67f4392eb822de0b403604055482aa7d03a53f65a36")
  gsub(/Q38_A17_VALIDATE_ONLY/, "Q38_A18_VALIDATE_ONLY")
  if ($0 == "expected_derived=f8c8be8a9d6cf2fb82658cf100018743ff001ae26462125482787d855b476662")
    print "expected_derived=8c527b18bb4074c527b890da0e38e5a9c21b877fa9770be2b7fc887999043b6d"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A18 trace supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A18 trace supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A18_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
