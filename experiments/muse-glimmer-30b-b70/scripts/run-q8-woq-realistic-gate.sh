#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 4 ]]; then
    echo "usage: $0 LABEL [realistic|parity] [N_PREDICT] [PROMPT]" >&2
    exit 2
fi

label=$1
mode=${2:-realistic}
n_predict=${3:-512}
parity_prompt=${4:-}
if [[ $mode != realistic && $mode != parity ]]; then
    echo "unsupported mode: $mode" >&2
    exit 2
fi
repo=/home/steve/llm-optimizations
source_root=/home/steve/src/llama.cpp-muse-100
binary=$source_root/build-sycl-b70-aot-bmg-g31/bin/llama-server
suite=$repo/experiments/muse-glimmer-30b-b70/realistic-suite-v1.json
model=/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/Muse-Glimmer-30B-UD-Q8_K_XL.gguf
draft=/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/dflash-bf16.gguf
run_dir=/mnt/fast-ai/bench-results/muse-glimmer-30b/realistic/$label
port=19494

if [[ -e $run_dir ]]; then
    echo "refusing to overwrite existing run: $run_dir" >&2
    exit 3
fi
mkdir -p "$run_dir"

set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u

exec 9>/run/lock/muse-glimmer-gpu-exclusive.lock
if ! flock -n 9; then
    echo "GPU host lock is busy" >&2
    exit 4
fi
printf 'muse-q8-realistic pid=%s label=%s\n' "$$" "$label" >&9

export ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3
export UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_ENABLE_VMM=1
export LLAMA_DFLASH_PROCESS_COMMITTED_ONLY=1
export LLAMA_DFLASH_TP_TOP_K=1
export LLAMA_DFLASH_CANDIDATE_TOP_K=1
export LLAMA_DFLASH_TP_GREEDY=0
export LLAMA_BACKEND_GREEDY_BATCH_ROWS=1
export LLAMA_TP_BACKEND_SAMPLING=1
export GGML_SYCL_COMM_ARGMAX=1
export GGML_SYCL_COMM_ARGMAX_REUSE_LOCAL=1
export GGML_SYCL_COMM_TOP_K=1
export GGML_SYCL_TOP_K_TREE_MERGE=1
export GGML_SYCL_TOP_K_BLOCK_SIZE=512
export GGML_SYCL_TOP_K_HEAP_SCAN=1
export GGML_SYCL_COMM_LAST_EVENT_READY=1
export GGML_SYCL_DNNL_FFN_BATCH2=1
export GGML_SYCL_DNNL_GEMM_CACHE=1
export GGML_SYCL_DNNL_GEMM_BIND_CACHE=1
export GGML_SYCL_BF16_GRAPH_CONVERSION_CACHE=0
export GGML_META_PARALLEL_SUBMIT=1
export GGML_META_PERSISTENT_PARALLEL_SUBMIT=0
export GGML_SYCL_Q8_0_WOQ_BF16=1
export GGML_SYCL_Q8_0_WOQ_FIXED16=1
export GGML_SYCL_RMS_NORM_MUL_ADD_FUSION=1
export GGML_SYCL_OP_PROFILE=0
export GGML_SYCL_DEVICE_TIMELINE=0
export GGML_SYCL_ENABLE_GRAPH=0

"$binary" \
    -m "$model" \
    --alias muse-glimmer-30b-q8-woq \
    --host 127.0.0.1 --port "$port" \
    -ngl 99 -c 32768 --parallel 1 -b 1024 -ub 1024 --threads 8 \
    -fa on --jinja -sm tensor -bs -lv 4 \
    --spec-type draft-dflash --spec-draft-model "$draft" \
    --spec-draft-n-max 15 --spec-draft-p-min 0 --spec-draft-ngl 99 \
    >"$run_dir/server.log" 2>&1 &
server_pid=$!

cleanup() {
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT

healthy=0
for _ in $(seq 1 180); do
    if ! kill -0 "$server_pid" 2>/dev/null; then
        echo "server exited during startup" >&2
        exit 5
    fi
    if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
        healthy=1
        break
    fi
    sleep 4
done
if [[ $healthy -ne 1 ]]; then
    echo "server did not become healthy" >&2
    exit 6
fi

if [[ $mode == realistic ]]; then
    python3 "$repo/scripts/bench-openai-realistic-suite.py" \
        --base-url "http://127.0.0.1:$port" \
        --model muse-glimmer-30b-q8-woq \
        --api-mode native \
        --suite "$suite" \
        --max-tokens 512 \
        --metric-tokens 100 \
        --seed 1 \
        --timeout 900 \
        --return-token-ids \
        --request-extra-json '{"cache_prompt":false,"backend_sampling":true,"samplers":["temperature"]}' \
        --out "$run_dir/realistic-suite.json" \
        >"$run_dir/bench.stdout.json"

    python3 "$repo/scripts/qualify_realistic_window_metrics.py" \
        "$run_dir/realistic-suite.json" --in-place \
        | tee "$run_dir/qualification.txt"

    sha256sum "$binary" "$(dirname "$binary")/libggml-sycl.so.0.19.0" "$suite" \
        "$run_dir/realistic-suite.json" "$run_dir/server.log" \
        >"$run_dir/SHA256SUMS"
else
    parity_args=(
        --base-url "http://127.0.0.1:$port"
        --out "$run_dir/parity.json"
        --n-predict "$n_predict"
    )
    if [[ -n $parity_prompt ]]; then
        parity_args+=(--prompt "$parity_prompt")
    fi
    python3 "$repo/experiments/muse-glimmer-30b-b70/scripts/check-q8-woq-spec-parity.py" \
        "${parity_args[@]}" \
        | tee "$run_dir/parity.stdout.json"
    sha256sum "$binary" "$(dirname "$binary")/libggml-sycl.so.0.19.0" \
        "$run_dir/parity.json" "$run_dir/server.log" \
        >"$run_dir/SHA256SUMS"
fi
