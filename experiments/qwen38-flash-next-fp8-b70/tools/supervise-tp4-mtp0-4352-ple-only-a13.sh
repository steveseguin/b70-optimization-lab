#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a10.sh"
expected_base=5cd9afd92c394ace579c8837c560b37f0dcedbb0e44c9fe5a268b89fdd870ac0
expected_source=21d301cb02882876e7b321e63437d6d1c872eb777dba56b39e4c2c909f02c75f

derive() {
  Q38_A10_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a10/, "ple-only-a13")
  gsub(/attempt10/, "attempt13")
  gsub(/19682/, "19685")
  gsub(/q38-ple4k-a10/, "q38-ple4k-a13")
  gsub(/Q38_A10_VALIDATE_ONLY/, "Q38_A13_VALIDATE_ONLY")
  gsub(/e5137bfd8ca2ca718c4fd93d86d54bb843e2999b/, "f68c9386fe5af54055bdf20684b269b9c1340e44")
  gsub(/ple-only-fresh-summary/, "ple-only-qsa-stable-summary")
  gsub(/PLE-only 4K MTP0 fresh-server repeat/, "PLE-only 4K MTP0 QSA-stable treatment")
  gsub(/8a693f850bb43e71f41258b9cd80915c6275c0f590ef12b6e3ed7c5d9e09a910/, "2b9557fd9713abe75e6a89d6ee5068f15520e9cc919e11de687dff07c292f7ad")
  gsub(/b11ce44155577d78b63451733218e48181c8c24155a8d72f0ca0a6267df5b707/, "0240ce9fd347e93d0f1b05087ac65ee26936e9026af573934d835daec05ab0c7")
  if ($0 == "expected_derived=31c29c1905bd98783988291e69013d9740312092dccc51c43cd94b463c809c32")
    print "expected_derived=320be0ce51096729d347c28be9dfa655879097203fc86d84fbe5d3d027cb1df0"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A13 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A13 supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A13_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
