#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a14.sh"
expected_base=f67349ed25cf8c3c38595813afd0ed3739d3e14dd24c8317d4994e969cb1fadd
expected_source=86c63e1d494ff9242a80069a5a655301d16231ce25ddcdcd0309ee58a895df70

derive() {
  Q38_A14_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a14/, "ple-only-a15")
  gsub(/q38-ple4k-a14/, "q38-ple4k-a15")
  gsub(/attempt14/, "attempt15")
  gsub(/19686/, "19687")
  gsub(/Q38_A14_VALIDATE_ONLY/, "Q38_A15_VALIDATE_ONLY")
  gsub(/de10733d6e46e2f54b1c024bd380737804f1d4ddcf363699756f383cec10c5ee/, "a9689bef6e14db3d3a1bcac77c53c42a51f888dd6cc663984c00da66b6dd2dfa")
  gsub(/2ea92230e4be419a38e89c67fecb60c173a89f1541e7a98c2fbc9d3a251db8b6/, "14c8e29c7bab28fa55b3e52db5092648f7702525220f8041d46840f214a0574f")
  if ($0 == "expected_derived=769ea881a71d04028c533353536cc96c5ded7a5703472812d0150bff282598d2")
    print "expected_derived=613f0813da13215ecff8987eb9da2d36f0f099e5b94416cc7d7256472c5ed825"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A15 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A15 supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A15_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
