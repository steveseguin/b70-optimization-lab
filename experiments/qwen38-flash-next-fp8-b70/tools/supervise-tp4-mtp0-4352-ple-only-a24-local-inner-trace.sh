#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a23-inner-trace.sh"
expected_base=8c4311a6dfe1fbd1f15d599119ae345ba6bdb7c2ee81cdecc41454fa74182ed3
expected_source=11e62aa1f1059590ed2466e9417071adb3720ef78457e23160a9c13dd4ac9c7a

derive() {
  Q38_A23_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a23/, "ple-only-a24")
  gsub(/attempt23/, "attempt24")
  gsub(/19695/, "19696")
  gsub(/Q38_A23_VALIDATE_ONLY/, "Q38_A24_VALIDATE_ONLY")
  gsub(/q38-ple4k-a23-rpc/, "q38-ple4k-a24-rpc")
  gsub(/9194d3065d2c6ad1fd0e86e6054d0dd398f3d2510f098090c0c06562bfe04874/, "23afbb401bc0ad15403e20e734ce5b5d9f4095b95a29e641a85e292659bbcff6")
  gsub(/04cee0d187065cdbcbd3a24195163f93e448c465324b71488bf4720c06fd9f8d/, "5c59942f2105649135a9123a67802c87c1a67f5e43810688cf579a7cf43b089e")
  gsub(/\/mnt\/usb-models\/llm-models\/Qwen3.8-Flash-Next-FP8/, "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8")
  if ($0 == "expected_derived=0a08c20662b0e031e4a2c222219e4d8d4e5cf20ffa37a7a1163d2190648ddc49")
    print "expected_derived=81e638e39a9902df0605a411b5f5b9d2d4a81f6c8f8545419621e99d56d5da80"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A24 local inner-trace supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A24 supervisor source %s\n' "$actual_source" >&2; exit 1; }
if [[ "${Q38_A24_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
