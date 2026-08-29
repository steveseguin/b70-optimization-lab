#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-16512-sampler-native-a6.sh"
derived=/tmp/q38-fn-sampler-native-client-a7.sh
expected_base=942e886f1726220f04e706f27a8a63eb252e8b7632b7636f1ea1d2f1c8dc71e1
expected_derived=718b9493ed44b22ce1b2495dbdd64dcd5f8522af43e1a6af4f9347ef3f309564

cleanup() { rm -f -- "$derived"; }
trap cleanup EXIT

[[ $# == 0 ]] || { printf 'FAIL: client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ ! -e "$derived" ]] || { printf 'FAIL: refusing to reuse %s\n' "$derived" >&2; exit 1; }
awk '{
  gsub(/attempt6/, "attempt7")
  gsub(/19678/, "19679")
  gsub(/sampler-native-a6/, "sampler-native-a7")
  print
}' "$base" >"$derived"
chmod 700 "$derived"
[[ "$(sha256sum "$derived" | cut -d' ' -f1)" == "$expected_derived" ]]
"$derived"
