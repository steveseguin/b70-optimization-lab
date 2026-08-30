#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-ep4-eager-mtp0-long-context-base.sh"
derived=/tmp/q38-ple4k-a9-base.sh
expected_base=d5ccc4d52220f7ef46f19202436edf56e0c40f125b1b807c84125df18093b5c1
expected_derived=973e14f4d94a58ec3551f2589b991cd62f410bf5bc93d399a194bbc7412edff0
campaign=qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1

cleanup() { rm -f -- "$derived"; }
trap cleanup EXIT

[[ $# == 0 ]] || { printf 'FAIL: launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ ! -e "$derived" ]] || { printf 'FAIL: refusing to reuse %s\n' "$derived" >&2; exit 1; }

awk '
$0 == "[[ \"${max_model_len}\" == \"16512\" ]] || {" {
  print "[[ \"${max_model_len}\" == \"4352\" ]] || {"
  next
}
$0 == "  printf '\''FAIL: long-context base is frozen to MAX_MODEL_LEN=16512\\n'\'' >&2" {
  print "  printf '\''FAIL: PLE-only base is frozen to MAX_MODEL_LEN=4352\\n'\'' >&2"
  next
}
$0 == "campaign=\"qwen38-flash-next-fp8-tp4-ep4-eager-mtp${mtp}${exact_suffix}-${max_model_len}-r1\"" {
  print "campaign=\"qwen38-flash-next-fp8-tp4-ep4-eager-mtp${mtp}${exact_suffix}-${max_model_len}-ple-only-r1\""
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
  print "rpc_dir=/tmp/q38-ple4k-a9-rpc"
  next
}
$0 == "expected_vllm_head=\"1372c62d975c554f4b465c8299bc5f3295301ceb\"" {
  print "expected_vllm_head=\"e5137bfd8ca2ca718c4fd93d86d54bb843e2999b\""
  next
}
/^[[:space:]]*'\''ple_embedding.ngram_embedding.weight'\'', '\''embed_tokens.weight'\''$/ {
  match($0, /^[[:space:]]*/)
  print substr($0, 1, RLENGTH) "'\''ple_embedding.ngram_embedding.weight'\'',"
  next
}
$0 == "embed_selector = '\''embed_tokens.weight'\''" { next }
index($0, "assert f'\''.{embed_selector}.'\''") == 1 { next }
$0 == "offload_bytes_per_rank = ple_bytes_per_rank + embed_bytes_per_rank" {
  print "offload_bytes_per_rank = ple_bytes_per_rank"
  next
}
$0 == "embed_bytes_per_rank = 317_849_600" { next }
$0 == "print(f'\''engine_config=tp4_ep4_triton_eager_mtp{mtp}_selective_ple_and_embed_uva'\'')" {
  print "print(f'\''engine_config=tp4_ep4_triton_eager_mtp{mtp}_selective_ple_only_uva'\'')"
  next
}
$0 == "print(f'\''embed_bytes_per_rank={embed_bytes_per_rank}'\'')" { next }
$0 == "assert offload_budget - offload_bytes_per_rank < 64 * 1024**2" {
  print "assert offload_budget - offload_bytes_per_rank < 96 * 1024**2"
  next
}
{
  gsub(/12\.25/, "12.0")
  gsub(/12\.22/, "11.92")
  gsub(/exact_12\.22/, "exact_11.92")
  gsub(/ple_embedding\.ngram_embedding\.weight,embed_tokens\.weight/, "ple_embedding.ngram_embedding.weight")
  gsub(/ple_embedding\.ngram_embedding\.weight embed_tokens\.weight/, "ple_embedding.ngram_embedding.weight")
  print
}
' "$base" >"$derived"
chmod 700 "$derived"
[[ "$(sha256sum "$derived" | cut -d' ' -f1)" == "$expected_derived" ]]
bash -n "$derived"
grep -Fxq '    max_model_len=int(os.environ['\''Q38_MAX_MODEL_LEN'\'']),' "$derived"
grep -Fxq '    enable_prefix_caching=False, offload_backend='\''uva'\'', cpu_offload_gb=12.0,' "$derived"
grep -Fxq "        'ple_embedding.ngram_embedding.weight'," "$derived"
grep -Fxq "assert config.offload_config.uva.cpu_offload_params == {" "$derived"
grep -Fxq "    'ple_embedding.ngram_embedding.weight'," "$derived"
grep -Fxq 'offload_bytes_per_rank = ple_bytes_per_rank' "$derived"
grep -Fxq 'offload_budget = int(12.0 * 1024**3)' "$derived"
grep -Fxq "print(f'engine_config=tp4_ep4_triton_eager_mtp{mtp}_selective_ple_only_uva')" "$derived"
grep -Fxq '  --cpu-offload-gb 12.0' "$derived"
grep -Fxq '  --cpu-offload-params ple_embedding.ngram_embedding.weight' "$derived"
grep -Fxq '  printf '\''cpu_offload_gb=12.0\n'\''' "$derived"
grep -Fxq '  printf '\''cpu_offload_params=ple_embedding.ngram_embedding.weight\n'\''' "$derived"
grep -Fxq 'expected_vllm_head="e5137bfd8ca2ca718c4fd93d86d54bb843e2999b"' "$derived"
grep -Fxq 'rpc_dir=/tmp/q38-ple4k-a9-rpc' "$derived"
grep -Fxq '[[ "${max_model_len}" == "4352" ]] || {' "$derived"
! grep -Fq "'embed_tokens.weight'" "$derived"
! grep -Fq -- '--cpu-offload-gb 12.25' "$derived"
! grep -Fq 'exact_12.22' "$derived"
if [[ "${Q38_A9_VALIDATE_ONLY:-0}" == 1 ]]; then
  sed -n '1,180p' "$derived"
  sed -n '320,510p' "$derived"
  exit 0
fi

export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
export VLLM_SRC=/home/steve/src/vllm-current-main
export KERNELS_SRC=/home/steve/src/vllm-xpu-kernels
export VLLM_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm
export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
export CACHE_PARENT=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70
export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=9 PORT=19681
export KV_CACHE_MEMORY_BYTES=134217728
export REASONING_PARSER=
unset PYTHONOPTIMIZE
"$derived" --execute --ack "RUN ${campaign}"
