#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a18-trace-client.sh"
expected_base=87597d379d9543af956ed67f4392eb822de0b403604055482aa7d03a53f65a36
expected_source=66799bd475c32c3a10b287bca21970260c6213774a337202fe98eb408b1e7a0a

derive() {
  Q38_A18_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a18/, "ple-only-a19")
  gsub(/attempt18/, "attempt19")
  gsub(/19690/, "19691")
  gsub(/Q38_A18_VALIDATE_ONLY/, "Q38_A19_VALIDATE_ONLY")
  gsub(/f2066bdfdc7b7596d08e704c9b522c9317993c17763f1651d63b83f43735e9a3/, "8a6a3b93981542bb340c6db8a940dc69ebf58e4335aa674dddf272080ad59897")
  if ($0 == "{ print }") {
    print "{"
    print "  gsub(/8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de/, \"268f6de4a3e4353191d4f75c48b6b0f243ca30196fcb4c582e1db2e2935db656\")"
    print "  print"
    print "}"
  } else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A19 trace client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A19 trace client source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A19_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
