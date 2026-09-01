#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a33-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a33-to-a34-fullgraph.py"
expected_base=776f608eee77fb8ad4b5d02496e9e68fa4e16392639e0fa471c857de5fffe02e
expected_rewriter=3dfd9bf23e83cd63fdb8eb1d367d9c601bc55d333ba4952869ffa5c778b60a7e
expected_derived=ca84bb3d2a5d7792313c9ee1584b9da2dbe06bc32b148a4fa31c43fd224e2033
expected_source=24f4d08a901f0c710acbb170e1971895e65833d43a4b5766d03fe47313d7de62

derive() {
  Q38_A33_SOURCE_ONLY=1 "$base" | \
    python3 "$rewriter" launcher --derived-hash "$expected_derived"
}

[[ $# == 0 ]] || { printf 'FAIL: A34 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A34 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A34_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
