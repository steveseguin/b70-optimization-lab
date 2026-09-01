#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
profile=${PROFILE:?set PROFILE to mtp0, mtp0-r50-control, mtp0-eager, mtp0-eager-defaultoff, mtp0-eager-defaultoff-tp1, mtp1, mtp1-fast, mtp1-serial-gdn, mtp1-serial-fp8, mtp1-serial-fa, or dynamic-mtp8}
attempt=${ATTEMPT:?set ATTEMPT to a unique fresh-server attempt label}
model_dir=${MODEL_DIR:?set MODEL_DIR to the verified Qwen3.8-27B-FP8 directory}
out_dir=${OUT_DIR:?set OUT_DIR to a new evidence directory}
cache_dir=${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a new empty compile-cache path}
suite=${SUITE:-${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}
readiness_timeout=${READINESS_TIMEOUT_S:-600}
cache_policy=${CACHE_POLICY:-fresh}
# R53/R54 established that fresh target and MTP1 runs are exact across
# independent caches when determinism is encoded in vLLM's compile context.
compilation_config=${COMPILATION_CONFIG:-'{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'}
export COMPILATION_CONFIG="${compilation_config}"

[[ ! -e "${out_dir}" ]] || {
  printf 'refusing to overwrite evidence: %s\n' "${out_dir}" >&2
  exit 1
}
case "${cache_policy}" in
  fresh)
    [[ ! -e "${cache_dir}" ]] || {
      printf 'fresh-cache attempt requires a new cache path: %s\n' "${cache_dir}" >&2
      exit 1
    }
    ;;
  compiled-kernel-replay)
    [[ -d "${cache_dir}" ]] || {
      printf 'compiled-kernel replay requires a populated cache directory: %s\n' "${cache_dir}" >&2
      exit 1
    }
    find "${cache_dir}" -type f -print -quit | grep -q . || {
      printf 'compiled-kernel replay cache is empty: %s\n' "${cache_dir}" >&2
      exit 1
    }
    ;;
  *)
    printf 'CACHE_POLICY must be fresh or compiled-kernel-replay\n' >&2
    exit 2
    ;;
esac
mkdir -p "${out_dir}"

case "${profile}" in
  mtp0)
    port=${PORT:-18131}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp0-${attempt}}
    served_model=qwen38-fp8
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-r15}"
      IMAGE_CONTRACT_PROFILE=mtp0
      EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID_OVERRIDE:-sha256:d19f802ba702a9cb94b155f807a4674a0100702aee838323372f740d7168e34e}"
      EXPECTED_KERNEL_HEAD="${EXPECTED_KERNEL_HEAD_OVERRIDE:-1e90ffa672ba02f17a909da11838a4c55b199783}"
      VLLM_XPU_FP8_BLOCK_W8A16=1
      VLLM_XPU_ENABLE_XPU_GRAPH=0
      TORCHINDUCTOR_DETERMINISTIC=1
      VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0
      VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0
      PYTHONHASHSEED=0
      VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
      CCL_P2P_ACCESS=1
      GPU_MEMORY_UTILIZATION=0.95
      MAX_MODEL_LEN=1024
      MAX_NUM_SEQS=1
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-server.sh"
    )
    ;;
  mtp0-r50-control)
    # Matched-image target for the R53/R54 MTP1 qualification matrix.  This
    # intentionally uses the same content-verified R50 userspace, kernel DSOs,
    # and mechanism defaults as mtp1-fast; only speculative decoding is absent.
    port=${PORT:-18131}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp0-r50-${attempt}}
    served_model=qwen38-fp8-strict-mtp0-r50
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50}"
      IMAGE_CONTRACT_PROFILE=mtp1-serial-fa-split-gdn
      EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID_OVERRIDE:?set EXPECTED_IMAGE_ID_OVERRIDE to the content-verified R50 image ID}"
      EXPECTED_KERNEL_HEAD="${EXPECTED_KERNEL_HEAD_OVERRIDE:-1e90ffa672ba02f17a909da11838a4c55b199783}"
      VLLM_XPU_FP8_BLOCK_W8A16=1
      VLLM_XPU_ENABLE_XPU_GRAPH=0
      TORCHINDUCTOR_DETERMINISTIC=1
      VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0
      VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0
      PYTHONHASHSEED=0
      VLLM_BATCH_INVARIANT=0
      VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0
      VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1
      VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0
      VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
      VLLM_XPU_GDN_NATIVE_FALLBACK=1
      CCL_P2P_ACCESS=1
      GPU_MEMORY_UTILIZATION=0.95
      MAX_MODEL_LEN=1024
      MAX_NUM_SEQS=1
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      SERVED_MODEL_NAME="${served_model}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-server.sh"
    )
    ;;
  mtp1)
    port=${PORT:-18132}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp1-${attempt}}
    served_model=qwen38-fp8-strict-mtp1
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122}"
      MAX_MODEL_LEN=1024
      MAX_NUM_SEQS=1
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      SERVED_MODEL_NAME="${served_model}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-server.sh"
    )
    ;;
  mtp1-fast)
    port=${PORT:-18132}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp1-fast-${attempt}}
    served_model=qwen38-fp8-strict-mtp1-fast
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50}"
      EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID_OVERRIDE:?set EXPECTED_IMAGE_ID_OVERRIDE to the content-verified R50 image ID}"
      EXPECTED_KERNEL_HEAD="${EXPECTED_KERNEL_HEAD_OVERRIDE:-1e90ffa672ba02f17a909da11838a4c55b199783}"
      ENFORCE_EAGER=0
      VLLM_XPU_ENABLE_XPU_GRAPH=0
      VLLM_XPU_FP8_BLOCK_W8A16=1
      VLLM_XPU_FP8_PACKED_SERIAL_EXACT=0
      VLLM_XPU_FA_SERIAL_SPEC_DECODE=0
      VLLM_XPU_FA_SERIAL_SPEC_NO_CAUSAL=0
      VLLM_BATCH_INVARIANT=0
      VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0
      VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1
      VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0
      VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT=0
      VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT=0
      VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
      VLLM_XPU_GDN_NATIVE_FALLBACK=1
      VLLM_XPU_MTP_SUPPRESS_BONUS_TOKEN=0
      VLLM_XPU_MTP_DRAFT_EAGER=0
      TORCHINDUCTOR_DETERMINISTIC=1
      VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0
      VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0
      PYTHONHASHSEED=0
      GPU_MEMORY_UTILIZATION=0.95
      MAX_MODEL_LEN=1024
      MAX_NUM_SEQS=1
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      SERVED_MODEL_NAME="${served_model}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-server.sh"
    )
    ;;
  mtp1-serial-gdn)
    port=${PORT:-18132}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp1-serial-gdn-${attempt}}
    served_model=qwen38-fp8-strict-mtp1-serial-gdn
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-gdn-r46}"
      EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID_OVERRIDE:?set EXPECTED_IMAGE_ID_OVERRIDE to the locally built R46 image ID}"
      EXPECTED_KERNEL_HEAD="${EXPECTED_KERNEL_HEAD_OVERRIDE:-1e90ffa672ba02f17a909da11838a4c55b199783}"
      ENFORCE_EAGER=0
      VLLM_XPU_ENABLE_XPU_GRAPH=0
      VLLM_XPU_FP8_BLOCK_W8A16=1
      VLLM_BATCH_INVARIANT=0
      VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0
      VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1
      VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1
      VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
      VLLM_XPU_GDN_NATIVE_FALLBACK=1
      VLLM_XPU_MTP_SUPPRESS_BONUS_TOKEN=0
      VLLM_XPU_MTP_DRAFT_EAGER=0
      TORCHINDUCTOR_DETERMINISTIC=1
      MAX_MODEL_LEN=1024
      MAX_NUM_SEQS=1
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      SERVED_MODEL_NAME="${served_model}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-server.sh"
    )
    ;;
  mtp1-serial-fp8)
    port=${PORT:-18132}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp1-serial-fp8-${attempt}}
    served_model=qwen38-fp8-strict-mtp1-serial-fp8
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-linear-r48}"
      EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID_OVERRIDE:?set EXPECTED_IMAGE_ID_OVERRIDE to the locally built R48 image ID}"
      EXPECTED_KERNEL_HEAD="${EXPECTED_KERNEL_HEAD_OVERRIDE:-1e90ffa672ba02f17a909da11838a4c55b199783}"
      ENFORCE_EAGER=0
      VLLM_XPU_ENABLE_XPU_GRAPH=0
      VLLM_XPU_FP8_BLOCK_W8A16=1
      VLLM_XPU_FP8_PACKED_SERIAL_EXACT=1
      VLLM_BATCH_INVARIANT=0
      VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0
      VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1
      VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0
      VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
      VLLM_XPU_GDN_NATIVE_FALLBACK=1
      VLLM_XPU_MTP_SUPPRESS_BONUS_TOKEN=0
      VLLM_XPU_MTP_DRAFT_EAGER=0
      TORCHINDUCTOR_DETERMINISTIC=1
      MAX_MODEL_LEN=1024
      MAX_NUM_SEQS=1
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      SERVED_MODEL_NAME="${served_model}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-server.sh"
    )
    ;;
  mtp1-serial-fa)
    port=${PORT:-18132}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp1-serial-fa-${attempt}}
    served_model=qwen38-fp8-strict-mtp1-serial-fa
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-attention-r49}"
      EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID_OVERRIDE:?set EXPECTED_IMAGE_ID_OVERRIDE to the locally built R49 image ID}"
      EXPECTED_KERNEL_HEAD="${EXPECTED_KERNEL_HEAD_OVERRIDE:-1e90ffa672ba02f17a909da11838a4c55b199783}"
      ENFORCE_EAGER=0
      VLLM_XPU_ENABLE_XPU_GRAPH=0
      VLLM_XPU_FP8_BLOCK_W8A16=1
      VLLM_XPU_FP8_PACKED_SERIAL_EXACT=0
      VLLM_XPU_FA_SERIAL_SPEC_DECODE=1
      VLLM_XPU_FA_SERIAL_SPEC_NO_CAUSAL=0
      VLLM_BATCH_INVARIANT=0
      VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0
      VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1
      VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0
      VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
      VLLM_XPU_GDN_NATIVE_FALLBACK=1
      VLLM_XPU_MTP_SUPPRESS_BONUS_TOKEN=0
      VLLM_XPU_MTP_DRAFT_EAGER=0
      TORCHINDUCTOR_DETERMINISTIC=1
      MAX_MODEL_LEN=1024
      MAX_NUM_SEQS=1
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      SERVED_MODEL_NAME="${served_model}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-server.sh"
    )
    ;;
  mtp0-eager)
    port=${PORT:-18134}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp0-eager-${attempt}}
    served_model=qwen38-fp8-strict-mtp0-eager
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122}"
      MAX_MODEL_LEN=1024
      MAX_NUM_SEQS=1
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      SERVED_MODEL_NAME="${served_model}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-eager-server.sh"
    )
    ;;
  mtp0-eager-defaultoff)
    port=${PORT:-18135}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp0-eager-defaultoff-${attempt}}
    served_model=qwen38-fp8-strict-mtp0-eager-defaultoff
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122}"
      VLLM_XPU_FP8_BLOCK_W8A16=0
      MAX_MODEL_LEN=1024
      MAX_NUM_SEQS=1
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      SERVED_MODEL_NAME="${served_model}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-eager-server.sh"
    )
    ;;
  mtp0-eager-defaultoff-tp1)
    port=${PORT:-18136}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp0-eager-defaultoff-tp1-${attempt}}
    served_model=qwen38-fp8-strict-mtp0-eager-defaultoff-tp1
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122}"
      MAX_MODEL_LEN=1024
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      SERVED_MODEL_NAME="${served_model}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/experiments/qwen38-27b-b70/scripts/run-20260827-qwen38-fp8-eager-defaultoff-tp1-server.sh"
    )
    ;;
  dynamic-mtp8)
    port=${PORT:-18133}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-dynamic-mtp8-${attempt}}
    served_model=qwen38-fp8-strict-dynamic-mtp8
    launcher=(
      env
      IMAGE="${IMAGE_OVERRIDE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1}"
      EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID_OVERRIDE:-sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6}"
      MAX_MODEL_LEN=1024
      MAX_NUM_SEQS=1
      MAX_NUM_BATCHED_TOKENS=1024
      PORT="${port}"
      CONTAINER_NAME="${container}"
      SERVED_MODEL_NAME="${served_model}"
      MODEL_DIR="${model_dir}"
      VLLM_CACHE_DIR="${cache_dir}"
      "${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-dynamic-mtp-server.sh"
    )
    ;;
  *)
    printf 'unsupported PROFILE: %s\n' "${profile}" >&2
    exit 2
    ;;
esac

if docker ps --format '{{.Names}}' | grep -Eq '^qwen38-'; then
  printf 'another Qwen container is already running\n' >&2
  docker ps --format '{{.Names}}' | grep -E '^qwen38-' >&2
  exit 1
fi
if ss -ltn | grep -Eq ":${port}[[:space:]]"; then
  printf 'port is already in use: %s\n' "${port}" >&2
  exit 1
fi

server_pid=
cleanup() {
  docker stop -t 30 "${container}" >/dev/null 2>&1 || true
  if [[ -n "${server_pid:-}" ]]; then
    wait "${server_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ "${cache_policy}" == compiled-kernel-replay ]]; then
  find "${cache_dir}" -type f -print0 | sort -z | xargs -0 sha256sum \
    >"${out_dir}/compile-cache-before.sha256"
fi

python3 - "${out_dir}/campaign-identity.json" "${profile}" "${attempt}" \
  "${model_dir}" "${cache_dir}" "${suite}" "${port}" "${container}" \
  "${cache_policy}" <<'PY'
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys

out, profile, attempt, model, cache, suite, port, container, cache_policy = sys.argv[1:]
suite_path = pathlib.Path(suite)
data = {
    "schema": "neural.download.qwen38-fp8-strict-attempt.v1",
    "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "profile": profile,
    "attempt": attempt,
    "model_dir": model,
    "fresh_compile_cache": cache,
    "compile_cache_policy": cache_policy,
    "compiled_kernel_cache_only": cache_policy == "compiled-kernel-replay",
    "prompt_kv_response_history_cache_reuse": False,
    "suite": str(suite_path),
    "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
    "port": int(port),
    "container": container,
    "gpu_memory_utilization": os.environ.get("GPU_MEMORY_UTILIZATION", "0.96"),
    "compilation_config_override": os.environ.get("COMPILATION_CONFIG"),
    "compiler_determinism_environment": {
        name: os.environ.get(name)
        for name in (
            "TORCHINDUCTOR_DETERMINISTIC",
            "PYTHONHASHSEED",
            "VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE",
            "VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING",
        )
    },
    "mechanism_environment": {
        name: os.environ.get(name)
        for name in (
            "VLLM_XPU_FP8_BLOCK_W8A16",
            "VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT",
            "VLLM_XPU_FA_SERIAL_SPEC_DECODE",
            "VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT",
            "VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT",
            "VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT",
            "VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH",
        )
    },
    "performance_contract": {
        "complete_fixed_suite": True,
        "max_tokens": 512,
        "metric_events": 100,
        "metric_intervals": 99,
        "aggregation": "median-of-prompt-class-medians",
        "cached_tokens_required": 0,
        "temperature": 0,
        "prompt_reuse": False,
        "ignore_eos": False,
    },
}
pathlib.Path(out).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY

"${launcher[@]}" >"${out_dir}/server.log" 2>&1 &
server_pid=$!

deadline=$((SECONDS + readiness_timeout))
until curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/health.json" 2>"${out_dir}/health.err"; do
  if ! kill -0 "${server_pid}" 2>/dev/null; then
    printf 'server exited before readiness; see %s\n' "${out_dir}/server.log" >&2
    tail -120 "${out_dir}/server.log" >&2 || true
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    printf 'server readiness timeout; see %s\n' "${out_dir}/server.log" >&2
    exit 1
  fi
  sleep 3
done

docker inspect "${container}" >"${out_dir}/container-inspect.json"
curl -fsS "http://127.0.0.1:${port}/v1/models" >"${out_dir}/models.json"

python3 "${repo}/scripts/bench-openai-realistic-suite.py" \
  --base-url "http://127.0.0.1:${port}" \
  --model "${served_model}" \
  --api-mode completions \
  --suite "${suite}" \
  --max-tokens 512 \
  --metric-tokens 100 \
  --seed 42 \
  --timeout 900 \
  --return-token-ids \
  --require-natural-eos \
  --request-extra-json '{"temperature":0,"top_p":1}' \
  --out "${out_dir}/performance.json" \
  >"${out_dir}/performance.stdout"

python3 "${repo}/scripts/neural-download-canaries.py" \
  --base-url "http://127.0.0.1:${port}" \
  --model "${served_model}" \
  --out "${out_dir}/canaries.json" \
  >"${out_dir}/canaries.stdout"

python3 - "${out_dir}/performance.json" "${out_dir}/canaries.json" <<'PY'
import json
import sys

d = json.load(open(sys.argv[1]))
canaries = json.load(open(sys.argv[2]))
gate = d["realistic_final_gate"]
fresh = d["fresh_response_validity"]
primary = d["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]
assert gate["passed"] and fresh["performance_gate_eligible"]
assert gate["cached_tokens_all_zero"]
assert len(d["rows"]) == 12
assert canaries["pass_all"], "independent canary gate failed"
print(f"class_balanced_median_tok_s={primary['median']:.12f}")
print(f"class_count={primary['count']}")
print("performance_workload_gate_passed=true")
print("independent_canary_gate_passed=true")
PY

curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/post-health.json"
trap - EXIT INT TERM
cleanup
if [[ "${cache_policy}" == compiled-kernel-replay ]]; then
  find "${cache_dir}" -type f -print0 | sort -z | xargs -0 sha256sum \
    >"${out_dir}/compile-cache-after.sha256"
fi
printf 'complete profile=%s attempt=%s evidence=%s\n' "${profile}" "${attempt}" "${out_dir}"
