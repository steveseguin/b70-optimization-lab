#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a15.sh"
expected_base=a9689bef6e14db3d3a1bcac77c53c42a51f888dd6cc663984c00da66b6dd2dfa
expected_source=d39133ae6d2e7a3ff186c6765877b3dfd55f69573a3c2e1363a60c9249f5d7f2

derive() {
  Q38_A15_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a15/, "ple-only-a16")
  gsub(/q38-ple4k-a15/, "q38-ple4k-a16")
  gsub(/attempt15/, "attempt16")
  gsub(/ATTEMPT=15 PORT=19687/, "ATTEMPT=16 PORT=19688")
  gsub(/19687/, "19688")
  gsub(/Q38_A15_VALIDATE_ONLY/, "Q38_A16_VALIDATE_ONLY")
  gsub(/f68c9386fe5af54055bdf20684b269b9c1340e44/, "9f720cd4aa6c8a8b045f54dfa10f5b8611caccbd")
  if ($0 == "expected_derived=6c98434db88f59a9383c88c9668ccde278e5926e14dd8160c86cb99a6269b753")
    print "expected_derived=274372861adf49f0a1a9506012a9047357c1eff572f8afadb24fc77b6d62356c"
  else
    print
  if ($0 == "export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
    print "export Q38_REPEATABILITY_TRACE_FILE=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt16/qwen4-exp-late-prefill-rank{rank}.json"
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A16 trace launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A16 trace launcher source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A16_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
