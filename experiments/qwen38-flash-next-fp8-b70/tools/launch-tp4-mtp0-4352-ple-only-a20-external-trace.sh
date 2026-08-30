#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a19-trace.sh"
expected_base=e93510a3e6b21ec9f0782783653d502ab4c3c7cad98f072f473a849c4b70ce5f
expected_source=76000b8c00eaf66ea735951e41f6233c64d7cd9af4317b8ea3194b5580d7ef35

derive() {
  Q38_A19_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a19/, "ple-only-a20")
  gsub(/q38-ple4k-a19/, "q38-ple4k-a20")
  gsub(/attempt19/, "attempt20")
  gsub(/ATTEMPT=19 PORT=19691/, "ATTEMPT=20 PORT=19692")
  gsub(/19691/, "19692")
  gsub(/Q38_A19_VALIDATE_ONLY/, "Q38_A20_VALIDATE_ONLY")
  gsub(/\/mnt\/fast-ai\/llm-models\/Qwen3.8-Flash-Next-FP8/, "/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8")
  if ($0 == "expected_derived=1338edcca066adcceec4ee1ea9082f24bf0d1d746ca28ceb7dcee1c1af7a7647")
    print "expected_derived=97b2680255034384a794c46159723b7bf44df200b15c8f0f0c9b4bc7764dcbcb"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A20 external trace launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A20 launcher source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A20_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
