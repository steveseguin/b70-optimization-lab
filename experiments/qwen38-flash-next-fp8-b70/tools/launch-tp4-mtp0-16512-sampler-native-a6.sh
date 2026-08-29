#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-ep4-eager-mtp0-long-context-base.sh"
derived=/tmp/q38-fn-sampler-native-base-a6.sh
expected_base=d5ccc4d52220f7ef46f19202436edf56e0c40f125b1b807c84125df18093b5c1
expected_derived=55974515c04f7790452238a7bd929d1b70dca6b0b1be95aa2ed49193e35bf393
attempt=6
port=19678
model=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8
campaign=qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-16512-sampler-native-r1

cleanup() {
  rm -f -- "$derived"
}
trap cleanup EXIT

[[ $# == 0 ]] || { printf 'FAIL: launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: frozen long-context base hash mismatch\n' >&2
  exit 1
}
[[ ! -e "$derived" ]] || { printf 'FAIL: refusing to reuse %s\n' "$derived" >&2; exit 1; }

awk '
$0 == "campaign=\"qwen38-flash-next-fp8-tp4-ep4-eager-mtp${mtp}${exact_suffix}-${max_model_len}-r1\"" {
  print "campaign=\"qwen38-flash-next-fp8-tp4-ep4-eager-mtp${mtp}${exact_suffix}-${max_model_len}-sampler-native-r1\""
  next
}
index($0, "script_dir=$(cd --") == 1 {
  print "script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools"
  next
}
index($0, "repo_root=$(cd --") == 1 {
  print "repo_root=/home/steve/llm-optimizations"
  next
}
{ print }
$0 == "export VLLM_KV_CACHE_LAYOUT=BLHNC" {
  print "export VLLM_XPU_USE_SAMPLER_KERNEL=0"
}
$0 == "  printf '\''kv_cache_layout=BLHNC\\n'\''" {
  print "  printf '\''xpu_sampler_kernel=0\\n'\''"
}
' "$base" >"$derived"
chmod 700 "$derived"
[[ "$(sha256sum "$derived" | cut -d' ' -f1)" == "$expected_derived" ]] || {
  printf 'FAIL: derived sampler-native launcher hash mismatch\n' >&2
  exit 1
}

export MODEL_PATH="$model"
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
export VLLM_SRC=/home/steve/src/vllm-current-main
export KERNELS_SRC=/home/steve/src/vllm-xpu-kernels
export VLLM_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm
export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
export CACHE_PARENT=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70
export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=16512 ATTEMPT="$attempt" PORT="$port"
export KV_CACHE_MEMORY_BYTES=358465536
export REASONING_PARSER=
unset PYTHONOPTIMIZE

"$derived" --execute --ack "RUN ${campaign}"
