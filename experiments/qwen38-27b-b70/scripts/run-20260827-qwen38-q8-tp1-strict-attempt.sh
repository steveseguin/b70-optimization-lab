#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
attempt=${ATTEMPT:?set ATTEMPT to a unique attempt label}
model_dir=${MODEL_DIR:?set MODEL_DIR to the Qwen3.8 GGUF directory}
build_dir=${BUILD_DIR:?set BUILD_DIR to the accepted TP1 build directory}
out_dir=${OUT_DIR:?set OUT_DIR to a new evidence directory}
port=${PORT:-18138}
suite=${SUITE:-${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}
model=${model_dir}/Qwen3.8-27B-Q8_0.gguf
server=${build_dir}/bin/llama-server
backend=${build_dir}/bin/libggml-sycl.so
expected_model=f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8
expected_server=35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545
expected_backend=0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ ! -e "${out_dir}" ]] || fail "refusing to overwrite ${out_dir}"
[[ -f "${model}" && -x "${server}" && -f "${backend}" ]] || fail 'model/runtime artifact missing'
[[ "$(sha256sum "${server}" | awk '{print $1}')" == "${expected_server}" ]] || fail 'llama-server SHA-256 mismatch'
[[ "$(sha256sum "${backend}" | awk '{print $1}')" == "${expected_backend}" ]] || fail 'SYCL backend SHA-256 mismatch'

exec 7>/run/lock/muse-glimmer-gpu-exclusive.lock
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>/tmp/b70-gpu0.lock
flock -n 9 || fail 'GPU0 lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'

mkdir -p "${out_dir}"
"${repo}/repro/qwen38-27b-q8-tp1-b70/verify-model-direct.sh" "${model_dir}" \
  --json "${out_dir}/model-verification.json" \
  >"${out_dir}/model-verification.stdout"

python3 - "${out_dir}/campaign-identity.json" "${attempt}" "${model}" "${server}" "${backend}" "${suite}" "${expected_model}" "${expected_server}" "${expected_backend}" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import sys

out, attempt, model, server, backend, suite, model_sha, server_sha, backend_sha = sys.argv[1:]
suite_path = pathlib.Path(suite)
value = {
    "schema": "neural.download.qwen38-q8-tp1-strict-attempt.v1",
    "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "attempt": attempt,
    "profile": "q8-tp1-reasoning-off-mtp0",
    "artifacts": {
        "model": {"path": model, "sha256": model_sha},
        "server": {"path": server, "sha256": server_sha},
        "backend": {"path": backend, "sha256": backend_sha},
        "suite": {"path": suite, "sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest()},
    },
    "contract": {
        "prompt_count": 12,
        "prompt_classes": 6,
        "max_tokens": 512,
        "metric_events": 100,
        "metric_intervals": 99,
        "cached_tokens_required": 0,
        "prompt_cache": False,
        "reasoning": "off",
        "mtp": 0,
        "tensor_parallel": 1,
        "gpu_index": 0,
    },
}
pathlib.Path(out).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY

server_pid=
cleanup() {
  if pgrep -x llama-server >/dev/null; then
    pkill -TERM -x llama-server 2>/dev/null || true
  fi
  if [[ -n "${server_pid:-}" ]]; then
    wait "${server_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

env \
  MODEL_DIR="${model_dir}" BUILD_DIR="${build_dir}" GPU_INDEX=0 \
  HOST_ADDR=127.0.0.1 PORT="${port}" \
  CTX_SIZE=8192 PARALLEL_SLOTS=1 THROUGHPUT_MODE=1 \
  "${repo}/repro/qwen38-27b-q8-tp1-b70/run-server.sh" \
  >"${out_dir}/server.log" 2>&1 &
server_pid=$!

for _ in $(seq 1 600); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/health.json" 2>"${out_dir}/health.err"; then break; fi
  kill -0 "${server_pid}" 2>/dev/null || fail 'server exited before readiness'
  sleep 2
done
curl -fsS "http://127.0.0.1:${port}/health" >/dev/null || fail 'server readiness timeout'
curl -fsS "http://127.0.0.1:${port}/props" >"${out_dir}/props.json" || true
llama_pid=$(pgrep -n -x llama-server)
tr '\0' ' ' <"/proc/${llama_pid}/cmdline" >"${out_dir}/server-command.txt"
printf '\n' >>"${out_dir}/server-command.txt"
tr '\0' '\n' <"/proc/${llama_pid}/environ" \
  | grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|SYCL_UR_USE_LEVEL_ZERO_V2=|ONEAPI_ROOT=|LD_LIBRARY_PATH=)' \
  | LC_ALL=C sort >"${out_dir}/runtime-environment.txt"

python3 "${repo}/scripts/bench-openai-realistic-suite.py" \
  --base-url "http://127.0.0.1:${port}" \
  --model qwen38-q8-tp1-reasoning-off \
  --api-mode native-raw \
  --suite "${suite}" \
  --max-tokens 512 --metric-tokens 100 --seed 42 --timeout 900 \
  --return-token-ids --require-natural-eos \
  --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0,"top_p":1}' \
  --out "${out_dir}/performance.json" \
  >"${out_dir}/performance.stdout"

python3 "${repo}/scripts/neural-download-canaries.py" \
  --base-url "http://127.0.0.1:${port}" \
  --model qwen38-q8-tp1-reasoning-off \
  --out "${out_dir}/canaries.json" >"${out_dir}/canaries.stdout"

python3 - "${out_dir}/performance.json" "${out_dir}/canaries.json" <<'PY'
import json
import sys

performance = json.load(open(sys.argv[1]))
canaries = json.load(open(sys.argv[2]))
gate = performance["realistic_final_gate"]
fresh = performance["fresh_response_validity"]
metric = performance["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]
assert gate["passed"] and fresh["valid"] and gate["cached_tokens_all_zero"]
assert len(performance["rows"]) == 12 and canaries["pass_all"]
print(f"class_balanced_median_tok_s={metric['median']:.12f}")
print("performance_and_canary_gates_passed=true")
PY

curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/post-health.json"
trap - EXIT INT TERM
cleanup
printf 'complete attempt=%s evidence=%s\n' "${attempt}" "${out_dir}"
