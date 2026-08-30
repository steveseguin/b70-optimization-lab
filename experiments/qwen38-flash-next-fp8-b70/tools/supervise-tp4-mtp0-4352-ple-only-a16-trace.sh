#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a15.sh"
expected_base=9bcfcb3ece113966657223cbfbd524a7533a8ae31e4f3d9818a1d490dceb1da8
expected_source=dea6b0c18dee0910797157dd09465ff61da11e394612302c00be65325f8d5494

derive() {
  Q38_A15_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a15/, "ple-only-a16")
  gsub(/attempt15/, "attempt16")
  gsub(/19687/, "19688")
  gsub(/f68c9386fe5af54055bdf20684b269b9c1340e44/, "9f720cd4aa6c8a8b045f54dfa10f5b8611caccbd")
  gsub(/launch-tp4-mtp0-4352-ple-only-a16\.sh/, "launch-tp4-mtp0-4352-ple-only-a16-trace.sh")
  gsub(/run-tp4-mtp0-4352-ple-only-a16-client\.sh/, "run-tp4-mtp0-4352-ple-only-a16-trace-client.sh")
  gsub(/a9689bef6e14db3d3a1bcac77c53c42a51f888dd6cc663984c00da66b6dd2dfa/, "0b5482ab292bf8f054fab026ad9a3c9eef9ef4a7522c17a74a16677b317f7f2b")
  gsub(/14c8e29c7bab28fa55b3e52db5092648f7702525220f8041d46840f214a0574f/, "171816212130fdc0453bf27f576015c88575c45ff87da8543f6cbe0608a6a4ac")
  gsub(/Q38_A15_VALIDATE_ONLY/, "Q38_A16_VALIDATE_ONLY")
  if ($0 == "expected_derived=613f0813da13215ecff8987eb9da2d36f0f099e5b94416cc7d7256472c5ed825")
    print "expected_derived=e0e0582e90be05e8c5336510a3d2601d328c52870a87f2d9f9d54bc2f119ca77"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A16 trace supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A16 trace supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A16_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
