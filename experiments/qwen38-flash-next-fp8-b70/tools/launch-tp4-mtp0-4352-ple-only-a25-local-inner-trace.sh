#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools
base="${script_dir}/launch-tp4-ep4-eager-mtp0-long-context-base.sh"
derived=/tmp/q38-ple4k-a25-base.sh
expected_base=d5ccc4d52220f7ef46f19202436edf56e0c40f125b1b807c84125df18093b5c1
expected_derived=b1048e3204d67d13944226f2714afb44f06a68f0c4d92477fbe0f49e1951b150
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
  print "rpc_dir=/tmp/q38-ple4k-a25-rpc"
  next
}
$0 == "expected_vllm_head=\"1372c62d975c554f4b465c8299bc5f3295301ceb\"" {
  print "expected_vllm_head=\"ca20c4465ca34fc733aac70416b75d7cb8a1c46f\""
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
  gsub(/diagnostics=none/, "diagnostics=qwen4exp-ple-inner-trace-rank-all")
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
grep -Fxq 'expected_vllm_head="ca20c4465ca34fc733aac70416b75d7cb8a1c46f"' "$derived"
grep -Fxq "  printf 'diagnostics=qwen4exp-ple-inner-trace-rank-all\n'" "$derived"
! grep -Fq "diagnostics=none" "$derived"
grep -Fxq 'rpc_dir=/tmp/q38-ple4k-a25-rpc' "$derived"
grep -Fxq '[[ "${max_model_len}" == "4352" ]] || {' "$derived"
! grep -Fq "'embed_tokens.weight'" "$derived"
! grep -Fq -- '--cpu-offload-gb 12.25' "$derived"
! grep -Fq 'exact_12.22' "$derived"
if [[ "${Q38_A25_VALIDATE_ONLY:-0}" == 1 ]]; then
  sed -n '1,180p' "$derived"
  sed -n '320,510p' "$derived"
  exit 0
fi

if [[ "${Q38_A25_VALIDATE_ONLY:-0}" != 1 ]]; then
  boot_id=$(< /proc/sys/kernel/random/boot_id)
  forbidden_boot_id=c9c86120-4735-4f7a-9500-d7e49f0d2f63
  [[ "$boot_id" != "$forbidden_boot_id" ]] || {
    printf 'FAIL: A25 requires a fresh boot after %s\n' "$forbidden_boot_id" >&2
    exit 1
  }
  mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
  swap_free_kib=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
  nvme_available_bytes=$(df -B1 --output=avail /mnt/fast-ai | tail -1 | tr -d ' ')
  (( mem_available_kib >= 120000000 )) || { printf 'FAIL: A25 requires MemAvailable >= 120000000 KiB\n' >&2; exit 1; }
  (( swap_free_kib >= 8000000 )) || { printf 'FAIL: A25 requires SwapFree >= 8000000 KiB\n' >&2; exit 1; }
  (( nvme_available_bytes >= 220000000000 )) || { printf 'FAIL: A25 requires >= 220000000000 free NVMe bytes\n' >&2; exit 1; }
  full_load_marker="/run/user/$(id -u)/q38-flash-next-full-load.boot-id"
  full_load_lock="${full_load_marker}.lock"
  exec 9>"$full_load_lock"
  flock -n 9 || { printf 'FAIL: another Flash-Next launch is claiming this boot\n' >&2; exit 1; }
  if [[ -e "$full_load_marker" ]] && [[ "$(< "$full_load_marker")" == "$boot_id" ]]; then
    printf 'FAIL: a Flash-Next full load is already marked in boot %s\n' "$boot_id" >&2
    exit 1
  fi
  marker_tmp="${full_load_marker}.tmp.$$"
  printf '%s\n' "$boot_id" >"$marker_tmp"
  mv "$marker_tmp" "$full_load_marker"
  flock -u 9
  exec 9>&-
fi

export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
export VLLM_SRC=/home/steve/src/vllm-current-main
export KERNELS_SRC=/home/steve/src/vllm-xpu-kernels
export VLLM_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm
export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
export Q38_REPEATABILITY_TRACE_FILE=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt25/qwen4-exp-late-prefill-rank{rank}.json
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK=all
export CACHE_PARENT=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70
export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=25 PORT=19697
export KV_CACHE_MEMORY_BYTES=134217728
export REASONING_PARSER=
unset PYTHONOPTIMIZE
"$derived" --execute --ack "RUN ${campaign}"
