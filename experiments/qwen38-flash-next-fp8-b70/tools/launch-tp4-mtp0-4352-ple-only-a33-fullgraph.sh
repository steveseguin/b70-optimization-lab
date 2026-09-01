#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a28-profile.sh"
rewriter="${script_dir}/rewrite-q38-a28-to-a33-fullgraph.py"
expected_base=492ac0b7cfb0d6f4c64fc2bd1e5ab1ec45222d2dd8ce118f50daeb0dce48f934
expected_rewriter=4ba75fb0eb0311b3feed20072fdceb30802c7425737b9405d22febcbd6b990aa
expected_derived=fd25c815e4acb95fdc08d5aed050885dcda072bf9028931a86ce89e4194acad0
expected_source=25a29499ff5ba55a13fd89292b852e93bdc07760cc14179e05f6f54887d7f07d

derive() {
  Q38_A28_SOURCE_ONLY=1 "$base" | \
    python3 "$rewriter" launcher --derived-hash "$expected_derived"
}

[[ $# == 0 ]] || { printf 'FAIL: A33 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A33 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A33_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
