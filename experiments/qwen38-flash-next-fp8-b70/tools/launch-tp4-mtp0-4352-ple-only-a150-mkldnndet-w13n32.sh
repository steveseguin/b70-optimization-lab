#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools
base="${script_dir}/launch-tp4-ep4-eager-mtp0-long-context-base.sh"
derived=/tmp/q38-ple2k-a150-base.sh
expected_base=d5ccc4d52220f7ef46f19202436edf56e0c40f125b1b807c84125df18093b5c1
expected_derived=c707308b68fc55d80da5b4fe4f20f153faf84e5d71728e466e1ffdebb23e93ed
campaign=qwen38-flash-next-fp8-tp4-ep4-mkldnndet-mtp0-4352-ple-only-r1
tuned_config_folder=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32
tuned_config_map='/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32/E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json'
[[ "$(sha256sum "$tuned_config_map" | cut -d' ' -f1)" == a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be ]] || { printf 'FAIL: A150 tuned M1 map drifted\n' >&2; exit 1; }
[[ "$(jq -r '."1".num_warps' "$tuned_config_map")" == 8 && "$(jq -r '."1".W1_CONFIG.BLOCK_SIZE_N' "$tuned_config_map")" == 32 && "$(jq -r '."1" | has("W2_CONFIG")' "$tuned_config_map")" == false ]] || { printf 'FAIL: A150 tuned M1 map entry is not the qualified W13-N32 shape\n' >&2; exit 1; }

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
  print "campaign=\"qwen38-flash-next-fp8-tp4-ep4-mkldnndet-mtp${mtp}${exact_suffix}-${max_model_len}-ple-only-r1\""
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
  print "rpc_dir=/tmp/q38-ple2k-a150-rpc"
  next
}
$0 == "expected_vllm_head=\"1372c62d975c554f4b465c8299bc5f3295301ceb\"" {
  print "expected_vllm_head=\"dad520873163b3c376241aa5dd968fa827161f1d\""
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
  print "print(f'\''engine_config=tp4_ep4_triton_mkldnndet_mtp{mtp}_selective_ple_only_uva'\'')"
  next
}
$0 == "print(f'\''embed_bytes_per_rank={embed_bytes_per_rank}'\'')" { next }
$0 == "assert offload_budget - offload_bytes_per_rank < 64 * 1024**2" {
  print "assert offload_budget - offload_bytes_per_rank < 96 * 1024**2"
  next
}
$0 == "unset VLLM_PLE_CPU_OFFLOAD" {
  print
  print "unset VLLM_XPU_PLE_UVA_PREFETCH"
  next
}
$0 == "  expected_kernels_head=\"ad25aa9f69a2171612b9c6b83dfa82c69559f9e4\"" {
  print "  expected_kernels_head=\"e421889999bc1e5a5f11044d14548b9afdba644d\""
  next
}
$0 == "export CCL_TOPO_P2P_ACCESS=1" {
  print
  print "export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32"
  print "export VLLM_XPU_MKLDNN_DETERMINISTIC=1"
  next
}
index($0, "diagnostics=none") > 0 {
  gsub(/diagnostics=none/, "diagnostics=mkldnndet-bundled-oneccl-torch-trace")
  print
  print "  printf '\''tuned_config_folder=moe-m1-w13-n32\\n'\''"
  print "  printf '\''mkldnn_deterministic=1\\n'\''"
  print "  printf '\''tuned_config_map_sha256=a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be\\n'\''"
  next
}
index($0, "if ! timeout 180s ") == 1 && index($0, "torch.distributed.run") > 0 {
  print ""
  print
  next
}
$0 == "setsid \"${vllm_bin}\" serve \"${args[@]}\" >\"${server_log}\" 2>&1 &" {
  print "[[ \"$(git -C \"${vllm_src}\" rev-parse HEAD)\" == \"${expected_vllm_head}\" ]] || fail \"vLLM overlay changed immediately before launch\""
  print "[[ -z \"$(git -C \"${vllm_src}\" status --porcelain)\" ]] || fail \"vLLM overlay became dirty immediately before launch\""
  print
  next
}
{
  gsub(/diagnostics=none/, "diagnostics=mkldnndet-bundled-oneccl-torch-trace")
  gsub(/moe_backend=triton eager=1/, "moe_backend=triton eager=1 graph=none")
  gsub(/qwen38-flash-next-fp8-tp4-ep4-eager-mtp/, "qwen38-flash-next-fp8-tp4-ep4-mkldnndet-mtp")
  gsub(/tp4_ep4_triton_eager_mtp/, "tp4_ep4_triton_mkldnndet_mtp")
  gsub(/First-load launcher/, "No-graph control launcher")
  gsub(/12\.25/, "12.0")
  gsub(/12\.22/, "11.92")
  gsub(/exact_12\.22/, "exact_11.92")
  gsub(/ple_embedding\.ngram_embedding\.weight,embed_tokens\.weight/, "ple_embedding.ngram_embedding.weight")
  gsub(/ple_embedding\.ngram_embedding\.weight embed_tokens\.weight/, "ple_embedding.ngram_embedding.weight")
  print
}
' "$base" >"$derived"
chmod 700 "$derived"
if [[ "${Q38_A150_DERIVED_SOURCE_ONLY:-0}" == 1 ]]; then cat "$derived"; exit 0; fi
[[ "$(sha256sum "$derived" | cut -d' ' -f1)" == "$expected_derived" ]]
bash -n "$derived"
grep -Fxq '    max_model_len=int(os.environ['\''Q38_MAX_MODEL_LEN'\'']),' "$derived"
grep -Fxq '    enable_prefix_caching=False, offload_backend='\''uva'\'', cpu_offload_gb=12.0,' "$derived"
grep -Fxq "        'ple_embedding.ngram_embedding.weight'," "$derived"
grep -Fxq "assert config.offload_config.uva.cpu_offload_params == {" "$derived"
grep -Fxq "    'ple_embedding.ngram_embedding.weight'," "$derived"
grep -Fxq 'offload_bytes_per_rank = ple_bytes_per_rank' "$derived"
grep -Fxq 'offload_budget = int(12.0 * 1024**3)' "$derived"
grep -Fxq "print(f'engine_config=tp4_ep4_triton_mkldnndet_mtp{mtp}_selective_ple_only_uva')" "$derived"
grep -Fxq '  --cpu-offload-gb 12.0' "$derived"
grep -Fxq '  --cpu-offload-params ple_embedding.ngram_embedding.weight' "$derived"
grep -Fxq '  printf '\''cpu_offload_gb=12.0\n'\''' "$derived"
grep -Fxq '  printf '\''cpu_offload_params=ple_embedding.ngram_embedding.weight\n'\''' "$derived"
grep -Fxq 'expected_vllm_head="dad520873163b3c376241aa5dd968fa827161f1d"' "$derived"
grep -Fxq "  printf 'diagnostics=mkldnndet-bundled-oneccl-torch-trace\n'" "$derived"
! grep -Fq "diagnostics=none" "$derived"
grep -Fxq 'rpc_dir=/tmp/q38-ple2k-a150-rpc' "$derived"
grep -Fxq '[[ "${max_model_len}" == "4352" ]] || {' "$derived"
! grep -Fq "'embed_tokens.weight'" "$derived"
! grep -Fq -- '--cpu-offload-gb 12.25' "$derived"
! grep -Fq 'exact_12.22' "$derived"
grep -Fxq 'export XPU_GRAPH=0' "$derived"
! grep -Fq 'VLLM_XPU_ENABLE_XPU_GRAPH=1' "$derived"
grep -Fxq '  --enforce-eager' "$derived"
! grep -Fq 'cudagraph_mode' "$derived"
! grep -Fq -- '--cudagraph-metrics' "$derived"
grep -Fq 'moe_backend=triton eager=1 graph=none mtp=%s' "$derived"
! grep -Fq 'graph=FULL_DECODE_ONLY' "$derived"
! grep -Fq 'oneccl-4ceafd1-b70-public' "$derived"
! grep -Fq 'CCL_SYCL_ALLREDUCE_LL' "$derived"
! grep -Fq 'CCL_KERNEL_PATH' "$derived"
! grep -Fq 'LD_PRELOAD=' "$derived"
[[ "$(grep -Fxc 'export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32' "$derived")" == 1 ]]
[[ "$(grep -Fxc "  printf 'tuned_config_folder=moe-m1-w13-n32\\n'" "$derived")" == 1 ]]
[[ "$(grep -Fxc 'export VLLM_XPU_MKLDNN_DETERMINISTIC=1' "$derived")" == 1 ]]
[[ "$(grep -Fxc "  printf 'mkldnn_deterministic=1\\n'" "$derived")" == 1 ]]
[[ "$(grep -Fxc "  printf 'tuned_config_map_sha256=a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be\\n'" "$derived")" == 1 ]]
! grep -Fq 'q38-flash-next-full-load.boot-id' "$derived"
! grep -Fq 'ep4-eager' "$derived"
! grep -Fq 'triton_eager' "$derived"
if [[ "${Q38_A150_VALIDATE_ONLY:-0}" == 1 ]]; then
  sed -n '1,180p' "$derived"
  sed -n '320,510p' "$derived"
  exit 0
fi

if [[ "${Q38_A150_VALIDATE_ONLY:-0}" != 1 ]]; then
  [[ "$(findmnt -no SOURCE,FSTYPE --target /mnt/usb-models)" == "/dev/sda2 fuseblk" ]] || {
    printf 'FAIL: A150 evidence mount is not /dev/sda2 fuseblk\n' >&2
    exit 1
  }
  [[ "$(findmnt -no SOURCE,FSTYPE --target /mnt/fast-ai)" == "/dev/nvme0n1p2 ext4" ]] || {
    printf 'FAIL: A150 model mount is not /dev/nvme0n1p2 ext4\n' >&2
    exit 1
  }
  expected_nvme_aer_cor=${Q38_A150_NVME_AER_BASELINE:-}
  expected_root_aer_cor=${Q38_A150_ROOT_AER_BASELINE:-}
  expected_nvme_sectors_read=${Q38_A150_NVME_SECTORS_READ_BASELINE:-}
  [[ "$expected_nvme_aer_cor" =~ ^[0-9]+$ && "$expected_root_aer_cor" =~ ^[0-9]+$ && \
     "$expected_nvme_sectors_read" =~ ^[0-9]+$ ]] || {
    printf 'FAIL: A150 requires numeric host-control AER baselines\n' >&2
    exit 1
  }
  mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
  swap_total_kib=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
  aspm_policy=$(< /sys/module/pcie_aspm/parameters/policy)
  nvme_aer_cor=$(awk '$1 == "TOTAL_ERR_COR" {print $2}' \
    /sys/bus/pci/devices/0000:01:00.0/aer_dev_correctable)
  root_aer_cor=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor)
  nvme_sectors_read=$(awk '$3 == "nvme0n1" {print $6}' /proc/diskstats)
  nvme_available_bytes=$(df -B1 --output=avail /mnt/fast-ai | tail -1 | tr -d ' ')
  (( mem_available_kib >= 120000000 )) || { printf 'FAIL: A150 requires MemAvailable >= 120000000 KiB\n' >&2; exit 1; }
  (( swap_total_kib == 0 )) || { printf 'FAIL: A150 requires disk-backed swap disabled\n' >&2; exit 1; }
  [[ "$aspm_policy" == *'[performance]'* ]] || { printf 'FAIL: A150 requires PCIe ASPM performance policy\n' >&2; exit 1; }
  (( root_aer_cor == expected_root_aer_cor && nvme_aer_cor >= expected_nvme_aer_cor && \
     nvme_aer_cor - expected_nvme_aer_cor <= 64 && \
     nvme_sectors_read >= expected_nvme_sectors_read && \
     nvme_sectors_read - expected_nvme_sectors_read <= 536870912 )) || {
    printf 'FAIL: A150 bounded local-NVMe guard failed\n' >&2; exit 1;
  }
  (( nvme_available_bytes >= 220000000000 )) || { printf 'FAIL: A150 requires >= 220000000000 free NVMe bytes\n' >&2; exit 1; }
fi

export MODEL_PATH=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
export VLLM_SRC=/home/steve/src/vllm-current-main
export KERNELS_SRC=/home/steve/src/vllm-xpu-kernels
export VLLM_PYTHON=/home/steve/.venvs/vllm-xpu/bin/python
export VLLM_BIN=/home/steve/.venvs/vllm-xpu/bin/vllm
export RUN_PARENT=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
export TORCH_TRACE=${RUN_PARENT}/qwen38-flash-next-fp8-tp4-ep4-mkldnndet-mtp0-4352-ple-only-r1-attempt150/torch-trace
unset Q38_REPEATABILITY_TRACE_FILE
unset VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK
unset VLLM_XPU_PLE_UVA_PREFETCH
export CACHE_PARENT=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70
export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=150 PORT=19821
export KV_CACHE_MEMORY_BYTES=134217728
export Q38_STEP_TIMING_LOG=10
export Q38_LAYER_TIMING_LOG=10
export Q38_MOE_GEMM_EVENT_TIMING=1
export REASONING_PARSER=
unset PYTHONOPTIMIZE
"$derived" --execute --ack "RUN ${campaign}"
