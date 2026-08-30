#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a19-trace-client.sh"
expected_base=b2fc8181b4877c0c05e0aca9dc52800aec866e44be25054657e107338bd8f5ef
expected_source=ad98b16cf2089790f57f85a9ad2d1fc618aeff7fd9164a91d844d4669c0f56c2

derive() {
  Q38_A19_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a19/, "ple-only-a20")
  gsub(/attempt19/, "attempt20")
  gsub(/19691/, "19692")
  gsub(/Q38_A19_VALIDATE_ONLY/, "Q38_A20_VALIDATE_ONLY")
  gsub(/8a6a3b93981542bb340c6db8a940dc69ebf58e4335aa674dddf272080ad59897/, "a1feb6d4e293873e6b494de30da4bcd280993aaad158db4fb400f33b8c9a8102")
  if (index($0, "gsub(/8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de/") != 0) {
    print
    print "  gsub(/\\/mnt\\/fast-ai\\/llm-models\\/Qwen3.8-Flash-Next-FP8/, \"/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8\")"
  } else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A20 external trace client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A20 client source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A20_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
