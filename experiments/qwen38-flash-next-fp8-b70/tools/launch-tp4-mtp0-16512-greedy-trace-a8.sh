#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-ep4-eager-mtp0-long-context-base.sh"
derived=/tmp/q38-gtrace-a8-base.sh
expected_base=d5ccc4d52220f7ef46f19202436edf56e0c40f125b1b807c84125df18093b5c1
expected_derived=ded085ed13530ba198cd2bbca24a2eeab09c17df62da77ff53ca398ddf0c3f7b
attempt=8
port=19680
model=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8
campaign=qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-16512-greedy-trace-r1

cleanup() { rm -f -- "$derived"; }
trap cleanup EXIT

[[ $# == 0 ]] || { printf 'FAIL: launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ ! -e "$derived" ]] || { printf 'FAIL: refusing to reuse %s\n' "$derived" >&2; exit 1; }

awk '
$0 == "campaign=\"qwen38-flash-next-fp8-tp4-ep4-eager-mtp${mtp}${exact_suffix}-${max_model_len}-r1\"" {
  print "campaign=\"qwen38-flash-next-fp8-tp4-ep4-eager-mtp${mtp}${exact_suffix}-${max_model_len}-greedy-trace-r1\""
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
$0 == "rpc_dir=\"/tmp/${campaign}-attempt${attempt}-rpc\"" {
  print "rpc_dir=/tmp/q38-gtrace-a8-rpc"
  next
}
$0 == "expected_vllm_head=\"1372c62d975c554f4b465c8299bc5f3295301ceb\"" {
  print "expected_vllm_head=\"5d5081b2b1e145067bce6ec99492eac7ce042e23\""
  next
}
$0 == "export VLLM_KV_CACHE_LAYOUT=BLHNC" {
  print
  print "export VLLM_XPU_USE_SAMPLER_KERNEL=1"
  print "export VLLM_GREEDY_DECISION_TRACE_DIR=\"${run_dir}/greedy-trace\""
  print "export VLLM_GREEDY_DECISION_TRACE_REQUEST_PREFIX=depth-qwen38-flash-next-bcd9f01-exact-depth-v1-depth-4096"
  print "export VLLM_GREEDY_DECISION_TRACE_MAX_RECORDS=256"
  print "export VLLM_GREEDY_DECISION_TRACE_TOPK=8"
  next
}
$0 == "assert envs.VLLM_KV_CACHE_LAYOUT == '\''BLHNC'\''" {
  print
  print "assert envs.VLLM_XPU_USE_SAMPLER_KERNEL is True"
  print "assert envs.VLLM_GREEDY_DECISION_TRACE_MAX_RECORDS == 256"
  print "assert envs.VLLM_GREEDY_DECISION_TRACE_TOPK == 8"
  next
}
$0 == "  printf '\''diagnostics=none\\n'\''" {
  print "  printf '\''xpu_sampler_kernel=1\\n'\''"
  print "  printf '\''diagnostics=greedy-decision-trace-top8-max256\\n'\''"
  next
}
{ print }
' "$base" >"$derived"
chmod 700 "$derived"
[[ "$(sha256sum "$derived" | cut -d' ' -f1)" == "$expected_derived" ]]

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
