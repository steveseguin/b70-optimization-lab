#!/usr/bin/env bash
set -euo pipefail

treatment="${1:?usage: run_qknorm_rope_crossover_leg.sh control|candidate RUN_DIR}"
run_dir="${2:?usage: run_qknorm_rope_crossover_leg.sh control|candidate RUN_DIR}"

case "$treatment" in
  control) qknorm_rope=0 ;;
  candidate) qknorm_rope=1 ;;
  *) echo "treatment must be control or candidate" >&2; exit 2 ;;
esac

case "$run_dir" in
  /media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/*) ;;
  *) echo "RUN_DIR must be a Laguna runs directory on CorsairExternal" >&2; exit 2 ;;
esac

if [[ -e "$run_dir" ]]; then
  echo "refusing to reuse existing run directory: $run_dir" >&2
  exit 2
fi

repo_root=/home/steve/llm-optimizations
vllm_root=/home/steve/src/deepseek-v4-vllm-xpu-dspark
kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
venv_python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
suite_rel=experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json
teacher=/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json
serve_script="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/serve_laguna.sh"
compare_script="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py"
base_url=http://127.0.0.1:18080

expected_vllm=d503073ec3573c6208cc2a06339815ec040ee984
expected_kernels=9525343e74b1a434b6af7d05583e1385a891c919
expected_suite=9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638
expected_teacher=d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1
expected_launcher=e3ae3956cdd48fda6ca9fa9c4b3040bac5b1caf6b6c6c743a4441695742c78ff
expected_comparator=87ad4d57907a15afba221be42ea00e3a1975308d421e0edc13881dafe38e3db3
expected_benchmark=40a483d9127a42c6e9f4a3651a429d39d25336d39eee0c782ba2c7712988aa2
expected_c=bd337e35e8c5735f7e7ab2e4ff97835931c86a6daa51241329c3997a6b61f5b4
expected_xpu_c=625af4bbe792effde9f2f54c319f807a5c49b9756be313f9307d90da9ff5149e
expected_moe_c=f222d3e2d2a8a331e3c85f12e0d02a17aa7a89147bbbcc8ac2c2a816629a405f
expected_grouped_gemm=78a7218de45ee46b3734dc977c0d6115607ff7536706c0be2d4728b4ca2c40be

actual_vllm="$(git -C "$vllm_root" rev-parse HEAD)"
actual_kernels="$(git -C "$kernel_root" rev-parse HEAD)"
actual_suite="$(sha256sum "$repo_root/$suite_rel" | awk '{print $1}')"
[[ "$actual_vllm" == "$expected_vllm" ]] || {
  echo "vLLM identity mismatch: $actual_vllm" >&2
  exit 3
}
[[ "$actual_kernels" == "$expected_kernels" ]] || {
  echo "kernel identity mismatch: $actual_kernels" >&2
  exit 3
}
[[ "$actual_suite" == "$expected_suite" ]] || {
  echo "suite identity mismatch: $actual_suite" >&2
  exit 3
}
check_hash() {
  local path="$1"
  local expected="$2"
  local actual
  actual="$(sha256sum "$path" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || {
    echo "SHA256 mismatch for $path: $actual" >&2
    exit 3
  }
}
check_hash "$teacher" "$expected_teacher"
check_hash "$serve_script" "$expected_launcher"
check_hash "$compare_script" "$expected_comparator"
check_hash "$repo_root/scripts/bench-openai-realistic-suite.py" "$expected_benchmark"
check_hash "$kernel_root/vllm_xpu_kernels/_C.abi3.so" "$expected_c"
check_hash "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" "$expected_xpu_c"
check_hash "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" "$expected_moe_c"
check_hash \
  "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" \
  "$expected_grouped_gemm"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || {
  echo "vLLM source tree is dirty" >&2
  exit 3
}
[[ -z "$(git -C "$kernel_root" status --short)" ]] || {
  echo "kernel source tree is dirty" >&2
  exit 3
}
if curl -fsS "$base_url/health" >/dev/null 2>&1; then
  echo "Laguna endpoint is already active" >&2
  exit 4
fi
if ss -H -ltn 'sport = :18080' | grep -q .; then
  echo "port 18080 already has a listener" >&2
  exit 4
fi
if pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1; then
  echo "an existing vLLM process is active" >&2
  exit 4
fi

mkdir -p "$run_dir"

export VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
export VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
export VLLM_XPU_LAGUNA_M8_QKNORM_ROPE="$qknorm_rope"
export VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0
export VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0
export VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0
export LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7
export LAGUNA_DFLASH_ROOT=/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/dflash-int4
export LAGUNA_GPU_MEMORY_UTILIZATION=0.90
export VLLM_EXTRA_ARGS=

{
  date -u +%Y-%m-%dT%H:%M:%SZ
  uname -a
  git -C "$repo_root" rev-parse HEAD
  git -C "$vllm_root" rev-parse HEAD
  git -C "$kernel_root" rev-parse HEAD
  sha256sum \
    "$kernel_root/vllm_xpu_kernels/_C.abi3.so" \
    "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" \
    "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" \
    "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so"
  printf '%s\n' \
    'VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1' \
    'VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1' \
    'VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1' \
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=$qknorm_rope" \
    'VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0' \
    'VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0' \
    'VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0' \
    'LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7' \
    'LAGUNA_GPU_MEMORY_UTILIZATION=0.90' \
    'VLLM_EXTRA_ARGS=' \
    'mode=dflash eager --no-async-scheduling kv=bfloat16 max_num_seqs=1' \
    "treatment=$treatment"
  sha256sum \
    "$repo_root/$suite_rel" \
    /media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/int4/config.json \
    /media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/dflash-int4/config.json
} > "$run_dir/identity.txt"

server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill -INT -- "-$server_pid" 2>/dev/null || true
    for _ in $(seq 1 30); do
      kill -0 "$server_pid" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$server_pid" 2>/dev/null; then
      kill -TERM -- "-$server_pid" 2>/dev/null || true
    fi
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

setsid "$serve_script" dflash "$run_dir" bfloat16 \
  > "$run_dir/server.log" 2>&1 &
server_pid="$!"
printf '%s\n' "$server_pid" > "$run_dir/server.pid"

ready=0
for _ in $(seq 1 180); do
  if curl -fsS "$base_url/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "service exited before becoming healthy" >&2
    tail -120 "$run_dir/server.log" >&2
    exit 5
  fi
  sleep 5
done
if (( ready == 0 )); then
  echo "service did not become healthy within 15 minutes" >&2
  tail -120 "$run_dir/server.log" >&2
  exit 5
fi

curl -fsS "$base_url/metrics" > "$run_dir/metrics-before-suite.prom"

cd "$repo_root"
"$venv_python" scripts/bench-openai-realistic-suite.py \
  --base-url "$base_url" \
  --model laguna-s-2.1-int4 \
  --suite "$suite_rel" \
  --max-tokens 512 \
  --metric-tokens 100 \
  --seed 1 \
  --timeout 1800 \
  --return-token-ids \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
  --out "$run_dir/bench.json" \
  | tee "$run_dir/bench.stdout"

curl -fsS "$base_url/metrics" > "$run_dir/metrics-after-suite.prom"

"$venv_python" "$compare_script" \
  --teacher "$teacher" \
  --candidate "$run_dir/bench.json" \
  --out "$run_dir/exactness-vs-q1.json" \
  > "$run_dir/exactness-vs-q1.stdout"

jq -e '
  .fresh_response_validity.valid == true and
  .fresh_response_validity.cached_tokens_all_zero == true and
  .fresh_response_validity.each_prompt_run_once == true and
  .realistic_final_gate.passed == true and
  .run_identity.seed == 1
' "$run_dir/bench.json" >/dev/null

cleanup
server_pid=""
trap - EXIT INT TERM

clean=0
for _ in $(seq 1 30); do
  if ! ss -H -ltn 'sport = :18080' | grep -q . \
    && ! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1; then
    clean=1
    break
  fi
  sleep 2
done
if (( clean == 0 )); then
  echo "vLLM processes or port 18080 remained after shutdown" >&2
  exit 6
fi

timeout 15 xpu-smi ps > "$run_dir/poststop-xpu-ps.txt"
if awk 'NR > 1 && $2 != "xpu-smi" {print; found=1} END {exit !found}' \
  "$run_dir/poststop-xpu-ps.txt" > "$run_dir/poststop-residual.txt"; then
  echo "non-probe XPU process remained after shutdown" >&2
  cat "$run_dir/poststop-residual.txt" >&2
  exit 6
fi

echo "completed $treatment leg: $run_dir"
