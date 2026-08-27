#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
profile=${PROFILE:?set PROFILE to mtp0, mtp1, or dynamic-mtp8}
attempt=${ATTEMPT:?set ATTEMPT to a unique fresh-server attempt label}
model_dir=${MODEL_DIR:?set MODEL_DIR to the verified Qwen3.8-27B-FP8 directory}
out_dir=${OUT_DIR:?set OUT_DIR to a new evidence directory}
cache_dir=${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a new empty compile-cache path}
suite=${SUITE:-${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}
readiness_timeout=${READINESS_TIMEOUT_S:-600}

[[ ! -e "${out_dir}" ]] || {
  printf 'refusing to overwrite evidence: %s\n' "${out_dir}" >&2
  exit 1
}
[[ ! -e "${cache_dir}" ]] || {
  printf 'fresh-server attempt requires a new cache path: %s\n' "${cache_dir}" >&2
  exit 1
}
mkdir -p "${out_dir}"

case "${profile}" in
  mtp0)
    port=${PORT:-18131}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp0-${attempt}}
    served_model=qwen38-fp8
    launcher=(
      env
      IMAGE=neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122
      VLLM_XPU_FP8_BLOCK_W8A16=1
      CCL_P2P_ACCESS=1
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
  mtp1)
    port=${PORT:-18132}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-mtp1-${attempt}}
    served_model=qwen38-fp8-strict-mtp1
    launcher=(
      env
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
  dynamic-mtp8)
    port=${PORT:-18133}
    container=${CONTAINER_NAME:-qwen38-fp8-strict-dynamic-mtp8-${attempt}}
    served_model=qwen38-fp8-strict-dynamic-mtp8
    launcher=(
      env
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

python3 - "${out_dir}/campaign-identity.json" "${profile}" "${attempt}" \
  "${model_dir}" "${cache_dir}" "${suite}" "${port}" "${container}" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import sys

out, profile, attempt, model, cache, suite, port, container = sys.argv[1:]
suite_path = pathlib.Path(suite)
data = {
    "schema": "neural.download.qwen38-fp8-strict-attempt.v1",
    "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "profile": profile,
    "attempt": attempt,
    "model_dir": model,
    "fresh_compile_cache": cache,
    "suite": str(suite_path),
    "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
    "port": int(port),
    "container": container,
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

python3 - "${out_dir}/performance.json" <<'PY'
import json
import sys

d = json.load(open(sys.argv[1]))
gate = d["realistic_final_gate"]
fresh = d["fresh_response_validity"]
primary = d["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]
assert gate["passed"] and fresh["performance_gate_eligible"]
assert gate["cached_tokens_all_zero"]
assert len(d["rows"]) == 12
print(f"class_balanced_median_tok_s={primary['median']:.12f}")
print(f"class_count={primary['count']}")
print("performance_workload_gate_passed=true")
PY

curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/post-health.json"
trap - EXIT INT TERM
cleanup
printf 'complete profile=%s attempt=%s evidence=%s\n' "${profile}" "${attempt}" "${out_dir}"
