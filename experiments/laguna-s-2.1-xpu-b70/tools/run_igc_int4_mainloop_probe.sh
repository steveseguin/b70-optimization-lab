#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 KERNEL_TREE NEW_OUTPUT_DIR" >&2
  exit 2
fi

kernel_tree=$1
output_dir=$2
deps_tree=${LAGUNA_XPU_DEPS_TREE:-$kernel_tree}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
probe_source="$script_dir/igc_int4_mainloop_probe.cpp"
compiler=/opt/intel/oneapi/compiler/2025.3/bin/icpx
torch_root=/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages/torch

for required in \
  "$probe_source" \
  "$compiler" \
  "$kernel_tree/csrc/sycl_first.h" \
  "$kernel_tree/csrc/xpu/grouped_gemm/xe_2/gemm_xe2.hpp" \
  "$deps_tree/.deps/cutlass-sycl-src/include" \
  "$torch_root/include"; do
  if [[ ! -e "$required" ]]; then
    echo "missing required path: $required" >&2
    exit 2
  fi
done

if [[ -e "$output_dir" ]]; then
  echo "refusing existing output directory: $output_dir" >&2
  exit 2
fi
mkdir -p -- "$output_dir"

IGC_ShaderDumpEnable=1 \
IGC_DumpToCustomDir="$output_dir" \
"$compiler" \
  -I"$kernel_tree/csrc" \
  -I"$kernel_tree" \
  -I"$deps_tree/.deps/cutlass-sycl-src/include" \
  -I"$deps_tree/.deps/cutlass-sycl-src/tools/util/include" \
  -I"$deps_tree/.deps/cutlass-sycl-src/applications" \
  -I"$kernel_tree/csrc/xpu/grouped_gemm/xe_2" \
  -I"$kernel_tree/csrc/xpu/grouped_gemm" \
  -isystem "$torch_root/include" \
  -isystem "$torch_root/include/torch/csrc/api/include" \
  -isystem /opt/intel/oneapi/compiler/2025.3/include \
  -isystem /opt/intel/oneapi/compiler/2025.3/include/sycl \
  -include "$kernel_tree/csrc/sycl_first.h" \
  -O3 \
  -DNDEBUG \
  -std=gnu++17 \
  -fsycl \
  -fsycl-targets=spir64_gen \
  -Xsycl-target-backend=spir64_gen \
  "-device bmg -internal_options -cl-intel-256-GRF-per-thread" \
  -Xspirv-translator \
  -spirv-ext=+SPV_INTEL_split_barrier,+SPV_INTEL_2d_block_io,+SPV_INTEL_subgroup_matrix_multiply_accumulate \
  -DVLLM_XPU_ENABLE_XE2 \
  -DCUTLASS_ENABLE_HEADERS_ONLY \
  -DCUTLASS_ENABLE_SYCL \
  -DSYCL_INTEL_TARGET \
  -DCUTLASS_VERSIONS_GENERATED \
  -fno-sycl-instrument-device-code \
  -Wno-unused-command-line-argument \
  "$probe_source" \
  -o "$output_dir/igc_int4_mainloop_probe"

shopt -s nullglob
assemblies=("$output_dir"/*.asm)
if [[ ${#assemblies[@]} -eq 0 ]]; then
  echo "IGC emitted no assembly dumps" >&2
  exit 1
fi

for assembly in "${assemblies[@]}"; do
  kernel=$(head -n 1 -- "$assembly")
  [[ "$kernel" == *LagunaInt4MainloopProbe* ]] || continue
  echo "kernel=$kernel"
  grep -m1 'instCount' "$assembly" || true
  printf 'dpas=%s mad_bf=%s mul_bf=%s mov_w=%s shr=%s bfn=%s spill_markers=%s\n' \
    "$(grep -cE '^[[:space:]]*dpas' "$assembly" || true)" \
    "$(grep -cE 'mad \(16\|M[0-9]+\).*:bf' "$assembly" || true)" \
    "$(grep -cE 'mul \(16\|M[0-9]+\).*:bf' "$assembly" || true)" \
    "$(grep -cE 'mov \(16\|M[0-9]+\).*:w ' "$assembly" || true)" \
    "$(grep -cE '^[[:space:]]*shr ' "$assembly" || true)" \
    "$(grep -cE '^[[:space:]]*bfn ' "$assembly" || true)" \
    "$(grep -ciE 'spill|scratch' "$assembly" || true)"
done
