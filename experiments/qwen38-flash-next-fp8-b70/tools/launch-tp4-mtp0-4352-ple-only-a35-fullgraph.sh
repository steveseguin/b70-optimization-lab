#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a34-fullgraph.sh"
rewriter="${script_dir}/rewrite-q38-a34-to-a35-fullgraph.py"
expected_base=6a2629debf63dc63c759d6c6eea34897ff7a0cc17b709febb1a7078499151531
expected_rewriter=037c4c7e4acdfa8ac621ff55bb114d027669598e7237a8699bd544f9d4f76375
expected_derived=6a21d4a751ff40299e772917447884c822fcff193bee6e23276db51ee2e045ca
expected_source=3bdc34e5a9c1b0da3edc45d6b8647d1fa0e30a14066152214d7f3444ed172449

derive() {
  Q38_A34_SOURCE_ONLY=1 "$base" | \
    python3 "$rewriter" launcher --derived-hash "$expected_derived"
}

[[ $# == 0 ]] || { printf 'FAIL: A35 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$rewriter" | cut -d' ' -f1)" == "$expected_rewriter" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A35 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A35_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
