#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a14.sh"
expected_base=de10733d6e46e2f54b1c024bd380737804f1d4ddcf363699756f383cec10c5ee
expected_source=f8d01f97b475c3bf411107ea2f1be9a34100928a340777162c0351490fe81339

derive() {
  Q38_A14_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a14/, "ple-only-a15")
  gsub(/q38-ple4k-a14/, "q38-ple4k-a15")
  gsub(/attempt14/, "attempt15")
  gsub(/ATTEMPT=14 PORT=19686/, "ATTEMPT=15 PORT=19687")
  gsub(/19686/, "19687")
  gsub(/Q38_A14_VALIDATE_ONLY/, "Q38_A15_VALIDATE_ONLY")
  if ($0 == "expected_derived=0c6e4c11f3ff0b2ae88d7a8437ca17c9987534b6109b2598979049351986e4cb")
    print "expected_derived=6c98434db88f59a9383c88c9668ccde278e5926e14dd8160c86cb99a6269b753"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A15 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A15 launcher source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A15_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
