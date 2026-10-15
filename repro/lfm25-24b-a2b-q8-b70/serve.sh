#!/usr/bin/env bash
# Run LFM2.5-24B-A2B Q8_0 on one Intel Arc Pro B70 in the foreground (Ctrl-C stops it).
#
#   BUILD_DIR=/path/to/build MODEL_DIR=/path/to/model repro/lfm25-24b-a2b-q8-b70/serve.sh [fast|reference]
#
# fast       (default) the exact fast path: about 2.7x the reference speed, same tokens and log-probabilities
# reference  llama.cpp's plain SYCL path (GGML_SYCL_DISABLE_OPT=1), the slow arm every fast-path output is checked against
#
# Optional: GPU (Level Zero device index, default 0), PORT (default 18110), HOST (default 127.0.0.1),
# CTX (context tokens, default 32768; the model accepts up to 128K), ALIAS (model name, default lfm25-24b-a2b).
set -euo pipefail

mode=${1:-fast}
build_dir=${BUILD_DIR:?set BUILD_DIR to the build directory from build.sh}
model=${MODEL_DIR:?set MODEL_DIR to the folder holding LFM2.5-24B-A2B-Q8_0.gguf}/LFM2.5-24B-A2B-Q8_0.gguf
[[ -x ${build_dir}/bin/llama-server ]] || { echo "No llama-server in ${build_dir}/bin" >&2; exit 2; }
[[ -f ${model} ]] || { echo "Model file not found: ${model}" >&2; exit 2; }

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
export ONEAPI_DEVICE_SELECTOR=level_zero:${GPU:-0}
export ZES_ENABLE_SYSMAN=1
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_DNNL_DETERMINISTIC=1
case ${mode} in
  fast)
    export GGML_SYCL_DISABLE_OPT=0               # reordered weight layouts (the speed)
    export GGML_SYCL_PRIORITIZE_DMMV=1           # keep plain Q8_0 matmuls on the reference kernel family ...
    export LLAMA_SYCL_DMMV_Q8_0_REORDER_EXACT=4  # ... reading the reordered layout with the reference arithmetic
    export LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1  # experts on the reordered layout ...
    export LLAMA_SYCL_MMVQ_ID_XOR_REDUCE=1       # ... summed in the reference order
    ;;
  reference)
    export GGML_SYCL_DISABLE_OPT=1
    ;;
  *) echo "mode must be fast or reference" >&2; exit 2 ;;
esac

exec "${build_dir}/bin/llama-server" -m "${model}" --alias "${ALIAS:-lfm25-24b-a2b}" \
  --host "${HOST:-127.0.0.1}" --port "${PORT:-18110}" -dev SYCL0 -ngl 99 \
  -c "${CTX:-32768}" -b 2048 -ub 512 -t 8 --poll 50 -ctk f16 -ctv f16 -fa on --reasoning auto \
  --parallel 1 --cache-ram 0 --ctx-checkpoints 0 --no-cache-prompt --slot-prompt-similarity 0 --fit off \
  --metrics --no-webui --jinja
