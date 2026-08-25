#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
model_dir="${MODEL_DIR:-}"
build_dir="${BUILD_DIR:-}"
out="${OUT:-${PWD}/qwen38-q8-tp1-depth.json}"
gpu="${GPU_INDEX:-0}"
[[ -n "${model_dir}" && -n "${build_dir}" ]] || { printf 'Set MODEL_DIR and BUILD_DIR.\n' >&2; exit 2; }
[[ ! -e "${out}" ]] || { printf 'Refusing to overwrite %s\n' "${out}" >&2; exit 2; }
"${script_dir}/verify-model-direct.sh" "${model_dir}"
set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR="level_zero:${gpu}"
export GGML_SYCL_ENABLE_GRAPH=0
export UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
export UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1
export GGML_SYCL_COMM_SINGLE_KERNEL=1 GGML_META_FUSE_ALLREDUCE_ADD=1 GGML_META_FUSE_ALLREDUCE_ADD_RMS_MUL=1
export GGML_SYCL_COMM_FUSED_Q8=1 GGML_SYCL_FUSED_SWIGLU_Q8=1 GGML_SYCL_FUSED_ATTN_Q8=1 GGML_SYCL_FUSED_GDN_Q8=1
export GGML_SYCL_FUSED_MMVQ_PAIR=1 GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K=1 GGML_SYCL_FUSED_MMVQ_PAIR_GDN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_ATTN=1 GGML_SYCL_FUSED_MMVQ_TRIPLE_GDN=1 GGML_SYCL_FUSED_MMVQ_QUAD_GDN=1
export GGML_SYCL_FUSED_GDN_BETA_SIGMOID=1 GGML_SYCL_FUSED_CONCAT_STATE=1 GGML_SYCL_FUSED_GDN_STATE_IO=1
export GGML_SYCL_FUSED_CONV_STATE_IO=1 GGML_SYCL_COMM_DIRECT_Q8=2 GGML_SYCL_FUSED_ROPE_SET_ROWS=1
export GGML_SYCL_COMM_REDUCE_VEC4=1 GGML_SYCL_FUSED_QK_NORM_ROPE=1 GGML_SYCL_FUSED_CONV_SILU_L2=1
export GGML_SYCL_FUSE_EXT=31 GGML_SYCL_QDEDUP_STATS=1 GGML_SYCL_MMQ_Q4K_REORDER=1
"${build_dir}/bin/llama-bench" -m "${model_dir}/Qwen3.8-27B-Q8_0.gguf" -dev SYCL0 -ngl 99 -sm layer \
  -p 2048 -n 128 -d 0,2048,4096,8192,16384,24576,32768 -b 2048 -ub 512 \
  -fa on -ctk f16 -ctv f16 -t 16 --poll 50 -r 5 -o json > "${out}"
python3 -B - "${out}" <<'PY'
import json,sys
rows=json.load(open(sys.argv[1],encoding='utf-8'))
assert len(rows)==14
assert all(len(r.get('samples_ts') or [])==5 for r in rows)
for r in rows:
    kind='pp2048' if r['n_prompt']==2048 else 'tg128'
    print(f"depth={r['n_depth']:5d} {kind}={r['avg_ts']:.6f} tok/s")
PY
