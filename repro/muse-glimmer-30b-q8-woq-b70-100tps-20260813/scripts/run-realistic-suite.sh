#!/usr/bin/env bash
set -euo pipefail

recipe_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_root=${LLAMA_CPP_ROOT:-"$HOME/src/llama.cpp-muse-q8-woq-repro"}
binary=${MUSE_BINARY:-"$source_root/build-sycl-b70-aot-bmg-g31/bin/llama-server"}
target=${MUSE_TARGET_MODEL:?set MUSE_TARGET_MODEL to the hash-pinned UD-Q8_K_XL GGUF}
draft=${MUSE_DRAFT_MODEL:?set MUSE_DRAFT_MODEL to the hash-pinned BF16 DFlash GGUF}
out_dir=${1:?usage: $0 NEW_OUTPUT_DIRECTORY}
port=${MUSE_PORT:-19494}
lock_path=${MUSE_GPU_LOCK_PATH:-/run/lock/muse-glimmer-gpu-exclusive.lock}

if [[ -e $out_dir ]]; then
    echo "refusing to overwrite $out_dir" >&2
    exit 2
fi
mkdir -p "$out_dir"
printf '%s  %s\n' e63bf23b7710ecdea2579e4b1de58980c4a2b446e8ecf48b782cfcefd2e31770 "$target" | sha256sum -c -
printf '%s  %s\n' 4a624b08e65047d94768f9ada606a1c42a1a7c08e05fc1ed0be876f1606b2ab2 "$draft" | sha256sum -c -

set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u

while IFS='=' read -r name _; do
    case "$name" in
        GGML_*|LLAMA_*|MUSE_*|UR_L0_*|ONEAPI_DEVICE_SELECTOR) unset "$name" ;;
    esac
done < <(env)

export ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3
export UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_ENABLE_VMM=1
export LLAMA_DFLASH_PROCESS_COMMITTED_ONLY=1
export LLAMA_DFLASH_TP_TOP_K=0
export LLAMA_DFLASH_CANDIDATE_TOP_K=1
export LLAMA_DFLASH_TP_GREEDY=1
export LLAMA_BACKEND_GREEDY_BATCH_ROWS=1
export LLAMA_TP_BACKEND_SAMPLING=1
export GGML_SYCL_COMM_ARGMAX=1
export GGML_SYCL_COMM_ARGMAX_REUSE_LOCAL=1
export GGML_SYCL_COMM_TOP_K=0
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
# Absence—not the string "0"—disables this profiler in the record source.
unset LLAMA_SPEC_PROFILE

exec 9>"$lock_path"
if ! flock -n 9; then
    echo "GPU host lock is busy" >&2
    exit 3
fi
printf 'muse-q8-realistic pid=%s out=%s\n' "$$" "$out_dir" >&9

command=(
    "$binary" -m "$target" --alias muse-glimmer-30b-q8-woq
    --host 127.0.0.1 --port "$port"
    -ngl 99 -c 32768 --parallel 1 -b 1024 -ub 1024 --threads 8
    -fa on --jinja -sm tensor -bs -lv 4
    --spec-type draft-dflash --spec-draft-model "$draft"
    --spec-draft-n-max 15 --spec-draft-p-min 0 --spec-draft-ngl 99
)
printf '%q ' "${command[@]}" >"$out_dir/command.txt"
printf '\n' >>"$out_dir/command.txt"
env | LC_ALL=C sort | rg '^(GGML_|LLAMA_|ONEAPI_DEVICE_SELECTOR|UR_L0_)' >"$out_dir/runtime.env"
"${command[@]}" >"$out_dir/server.log" 2>&1 &
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
        exit 4
    fi
    if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
        healthy=1
        break
    fi
    sleep 4
done
if [[ $healthy != 1 ]]; then
    echo "server did not become healthy" >&2
    exit 5
fi

python3 "$recipe_root/scripts/bench-openai-realistic-suite.py" \
    --base-url "http://127.0.0.1:$port" \
    --model muse-glimmer-30b-q8-woq \
    --api-mode native \
    --suite "$recipe_root/configs/realistic-suite-v1.json" \
    --max-tokens 512 --metric-tokens 100 --seed 1 --timeout 900 \
    --return-token-ids \
    --request-extra-json '{"cache_prompt":false,"backend_sampling":true,"samplers":["temperature"]}' \
    --out "$out_dir/realistic-suite.json" >"$out_dir/bench.stdout.json"
python3 "$recipe_root/scripts/qualify-realistic-window-metrics.py" \
    "$out_dir/realistic-suite.json" --in-place | tee "$out_dir/qualification.txt"
python3 "$recipe_root/scripts/bootstrap-realistic.py" \
    "$out_dir/realistic-suite.json" >"$out_dir/bootstrap.json"

# Stop first, then hash. The historical helper did this in the opposite order,
# so its intermediate SHA256SUMS entry for server.log was stale.
cleanup
trap - EXIT
sha256sum "$binary" "$(dirname "$binary")/libggml-sycl.so.0.19.0" \
    "$target" "$draft" "$recipe_root/configs/realistic-suite-v1.json" \
    "$out_dir/realistic-suite.json" "$out_dir/server.log" \
    >"$out_dir/SHA256SUMS"

jq -e '.realistic_final_gate.passed == true and .fresh_response_validity.cached_tokens_all_zero == true and .summary.tok_s_1_100_intervals_after_ttft.count == 15 and .summary.tok_s_1_100_intervals_after_ttft.median > 100' \
    "$out_dir/realistic-suite.json" >/dev/null
jq -e '.one_sided_95_lower_tok_s > 100' "$out_dir/bootstrap.json" >/dev/null
echo "realistic gate passed: $out_dir"
