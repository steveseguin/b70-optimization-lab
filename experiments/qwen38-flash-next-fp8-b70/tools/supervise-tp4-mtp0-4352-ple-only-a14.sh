#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a13.sh"
expected_base=d5ce14b5021681d72a9a9b1d61bd5c6a6df1b1621ea55dd70c03d38b786c2454
expected_source=ee4c46d43bf98e6a6e14e5c8736aed8294b201d72adf08b206a53aefd6f81559

derive() {
  Q38_A13_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a13/, "ple-only-a14")
  gsub(/q38-ple4k-a13/, "q38-ple4k-a14")
  gsub(/attempt13/, "attempt14")
  gsub(/19685/, "19686")
  gsub(/Q38_A13_VALIDATE_ONLY/, "Q38_A14_VALIDATE_ONLY")
  gsub(/2b9557fd9713abe75e6a89d6ee5068f15520e9cc919e11de687dff07c292f7ad/, "de10733d6e46e2f54b1c024bd380737804f1d4ddcf363699756f383cec10c5ee")
  gsub(/0240ce9fd347e93d0f1b05087ac65ee26936e9026af573934d835daec05ab0c7/, "2ea92230e4be419a38e89c67fecb60c173a89f1541e7a98c2fbc9d3a251db8b6")
  if ($0 == "expected_derived=320be0ce51096729d347c28be9dfa655879097203fc86d84fbe5d3d027cb1df0")
    print "expected_derived=769ea881a71d04028c533353536cc96c5ded7a5703472812d0150bff282598d2"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A14 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A14 supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A14_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
