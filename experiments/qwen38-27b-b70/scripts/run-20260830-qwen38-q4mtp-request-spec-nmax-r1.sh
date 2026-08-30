#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
target_dir=${TARGET_DIR:?set TARGET_DIR}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR}
build_dir=${BUILD_DIR:?set BUILD_DIR}
arm=${ARM:?set ARM to strict-mtp0, strict-mtp2, hybrid-r1, or hybrid-r2}
out_dir=${OUT_DIR:?set OUT_DIR to a new evidence directory}
oracle_json=${ORACLE_JSON:-}
port=${PORT:-18147}
prereg=${PREREG:-${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4mtp-request-spec-nmax-r1-prereg.json}

target=${target_dir}/Qwen3.8-27B-Q4_K_M.gguf
draft=${draft_dir}/mtp-Qwen3.8-27B-Q4_0.gguf
server=${build_dir}/bin/llama-server
backend=${build_dir}/bin/libggml-sycl.so
server_impl=${build_dir}/bin/libllama-server-impl.so
launcher=${repo}/repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
bench=${repo}/repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/bench.sh
suite=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
oracle_digests=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-concurrency-oracle-digests.json
harness=${repo}/scripts/bench-openai-concurrency-oracle.py
semantic_canary=${repo}/experiments/qwen38-27b-b70/scripts/qwen38-concurrent-quality-canary.py
sequential_canary=${repo}/scripts/neural-download-canaries.py
candidate_patch=${repo}/experiments/qwen38-27b-b70/patches/llama-cpp-request-spec-nmax-candidate-20260830.patch

expected_target=31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34
expected_draft=50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e
expected_server=408e3b3cc1e4f48e5d955d5acf72444e0f1ddfaf5802c19f3d69b181bb8eecb9
expected_backend=256312e871752d4ba3af09704843eb08efbd46e35d42ee04dfe4ec81d17e687f
expected_server_impl=c8c0e5d701445f6f8ca43f3cc0dfcfd6de5d70b2314b77d3bdf88ace6e6314fb
expected_patch=4091ebd53fcae8dd952a3b8f96b5df2248e2d363d92ff7350694df56be6fbdc3

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
case ${arm} in
  strict-mtp0|strict-mtp2|hybrid-r1|hybrid-r2) ;;
  *) fail 'invalid ARM' ;;
esac
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'
[[ ! -e "${out_dir}" ]] || fail "refusing to overwrite ${out_dir}"
if [[ "${arm}" == strict-mtp2 && -z "${oracle_json}" ]]; then
  fail 'strict-mtp2 requires ORACLE_JSON from strict-mtp0'
fi

check_hash() {
  local expected=$1 path=$2 actual
  [[ -f "${path}" ]] || fail "missing ${path}"
  actual=$(sha256sum "${path}" | awk '{print $1}')
  [[ "${actual}" == "${expected}" ]] || fail "identity mismatch: ${path}"
}

for path in "${prereg}" "${launcher}" "${bench}" "${suite}" "${oracle_digests}" \
  "${harness}" "${semantic_canary}" "${sequential_canary}"; do
  [[ -f "${path}" ]] || fail "missing ${path}"
done
check_hash "${expected_target}" "${target}"
check_hash "${expected_draft}" "${draft}"
check_hash "${expected_server}" "${server}"
check_hash "${expected_backend}" "${backend}"
check_hash "${expected_server_impl}" "${server_impl}"
check_hash "${expected_patch}" "${candidate_patch}"

exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'
mkdir -p "${out_dir}"

sha256sum "${target}" "${draft}" "${server}" "${backend}" "${server_impl}" \
  "${candidate_patch}" "${prereg}" "${launcher}" "${bench}" "${suite}" \
  "${oracle_digests}" "${harness}" "${semantic_canary}" "${sequential_canary}" \
  >"${out_dir}/sha256sums.txt"
free -b >"${out_dir}/memory-before.txt"
xpu-smi dump --device 0,1 --metrics MEMORY,POWER --number 1 >"${out_dir}/xpu-before.txt" 2>&1 || true

server_job=
cleanup() {
  if [[ -n "${server_job}" ]] && kill -0 "${server_job}" 2>/dev/null; then
    kill -INT "${server_job}" 2>/dev/null || true
    wait "${server_job}" 2>/dev/null || true
  fi
  local pid
  pid=$(pgrep -n -x llama-server || true)
  if [[ -n "${pid}" ]]; then
    kill -TERM "${pid}" 2>/dev/null || true
    for _ in $(seq 1 60); do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.5
    done
  fi
  free -b >"${out_dir}/memory-after.txt" 2>/dev/null || true
  xpu-smi dump --device 0,1 --metrics MEMORY,POWER --number 1 >"${out_dir}/xpu-after.txt" 2>&1 || true
}
trap cleanup EXIT INT TERM

start_server() {
  local depth=$1 slots=$2 context=$3
  timeout --signal=INT --kill-after=30s 5400s env \
    TARGET_DIR="${target_dir}" DRAFT_DIR="${draft_dir}" BUILD_DIR="${build_dir}" \
    ALLOW_REBUILT_BINARIES=1 MTP_DEPTH="${depth}" PORT="${port}" \
    CTX_SIZE="${context}" PARALLEL_SLOTS="${slots}" BATCH_SIZE=1024 UBATCH_SIZE=256 THREADS=8 \
    "${launcher}" >"${out_dir}/server.log" 2>&1 &
  server_job=$!
  local healthy=0
  for _ in $(seq 1 600); do
    if curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/health.json" 2>/dev/null; then
      healthy=1
      break
    fi
    kill -0 "${server_job}" 2>/dev/null || break
    sleep 1
  done
  (( healthy == 1 )) || fail 'server did not become healthy'
  local pid
  pid=$(pgrep -n -x llama-server || true)
  [[ -n "${pid}" ]] || fail 'healthy endpoint has no llama-server process'
  tr '\0' ' ' <"/proc/${pid}/cmdline" >"${out_dir}/server-command.txt"
  printf '\n' >>"${out_dir}/server-command.txt"
  tr '\0' '\n' <"/proc/${pid}/environ" |
    grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|SYCL_UR_USE_LEVEL_ZERO_V2=|ONEAPI_ROOT=|LD_LIBRARY_PATH=)' |
    LC_ALL=C sort >"${out_dir}/runtime-environment.txt"
  curl -fsS "http://127.0.0.1:${port}/props" >"${out_dir}/props.json"
  curl -fsS "http://127.0.0.1:${port}/slots" >"${out_dir}/slots-before.json"
}

metric_value() {
  local file=$1 metric=$2
  awk -v wanted="${metric}" '$1 == wanted { print $2; found=1 } END { if (!found) exit 1 }' "${file}"
}

if [[ "${arm}" == strict-mtp0 || "${arm}" == strict-mtp2 ]]; then
  depth=0
  [[ "${arm}" == strict-mtp2 ]] && depth=2
  start_server "${depth}" 1 8192
  env BASE_URL="http://127.0.0.1:${port}" OUT_DIR="${out_dir}/strict" \
    MTP_DEPTH="${depth}" ORACLE_JSON="${oracle_json}" "${bench}" |
    tee "${out_dir}/bench.stdout"
  curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-after.txt"
  curl -fsS "http://127.0.0.1:${port}/slots" >"${out_dir}/slots-after.json"
  printf '{"arm":"%s","qualified":true,"mtp_depth":%s}\n' "${arm}" "${depth}" \
    >"${out_dir}/qualification.json"
else
  start_server 2 64 32768
  curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-before-nmax0.txt"

  python3 "${harness}" \
    --base-url "http://127.0.0.1:${port}" \
    --model "qwen38-q4mtp-request-nmax0-${arm}" --api-mode native \
    --suite "${suite}" --concurrency 4,8,16,32,64 --repeats 1 --max-tokens 128 \
    --seed 42 --timeout 900 --return-token-ids --oracle-digests "${oracle_digests}" \
    --request-id-prefix "qwen38-q4mtp-request-nmax0-${arm}" \
    --request-extra-json '{"cache_prompt":false,"ignore_eos":true,"temperature":0,"speculative.n_max":0}' \
    --out "${out_dir}/nmax0-performance.json" | tee "${out_dir}/nmax0-performance.stdout"

  python3 "${semantic_canary}" \
    --base-url "http://127.0.0.1:${port}" --model "qwen38-q4mtp-request-nmax0-${arm}" \
    --concurrency 64 --rounds 2 --timeout 900 --speculative-n-max 0 \
    --request-id-prefix "qwen38-q4mtp-request-nmax0-${arm}-semantic" \
    --output-json "${out_dir}/nmax0-concurrent-quality-canary.json" |
    tee "${out_dir}/nmax0-concurrent-quality-canary.stdout"
  curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-after-nmax0.txt"

  python3 "${harness}" \
    --base-url "http://127.0.0.1:${port}" \
    --model "qwen38-q4mtp-request-nmax2-${arm}" --api-mode native \
    --suite "${suite}" --concurrency 1,2 --repeats 1 --max-tokens 128 \
    --seed 42 --timeout 900 --return-token-ids --oracle-digests "${oracle_digests}" \
    --request-id-prefix "qwen38-q4mtp-request-nmax2-${arm}" \
    --request-extra-json '{"cache_prompt":false,"ignore_eos":true,"temperature":0,"speculative.n_max":2}' \
    --out "${out_dir}/nmax2-performance.json" | tee "${out_dir}/nmax2-performance.stdout"
  python3 "${sequential_canary}" --base-url "http://127.0.0.1:${port}" \
    --model "qwen38-q4mtp-default-${arm}" --out "${out_dir}/default-mtp2-canaries.json"
  curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-after-nmax2.txt"
  curl -fsS "http://127.0.0.1:${port}/slots" >"${out_dir}/slots-after.json"

  before=$(metric_value "${out_dir}/metrics-before-nmax0.txt" llamacpp:spec_decode_num_draft_tokens_total)
  after_zero=$(metric_value "${out_dir}/metrics-after-nmax0.txt" llamacpp:spec_decode_num_draft_tokens_total)
  after_two=$(metric_value "${out_dir}/metrics-after-nmax2.txt" llamacpp:spec_decode_num_draft_tokens_total)
  python3 - "${out_dir}" "${before}" "${after_zero}" "${after_two}" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
before, after_zero, after_two = map(float, sys.argv[2:])
zero = json.load(open(root / "nmax0-performance.json"))
two = json.load(open(root / "nmax2-performance.json"))
canary = json.load(open(root / "nmax0-concurrent-quality-canary.json"))
default_canary = json.load(open(root / "default-mtp2-canaries.json"))

def qualify_performance(doc):
    batches = doc["batches"]
    rows = [row for batch in batches for row in batch["rows"]]
    accepted = {
        "output-identity-qualified",
        "output-isolation-qualified-shape-variant",
    }
    return {
        "qualified": (
            all(row.get("completion_tokens") == 128 for row in rows)
            and all(batch.get("cached_tokens_all_zero") for batch in batches)
            and all(batch.get("complete_token_id_identity_all") for batch in batches)
            and sum(batch.get("cross_base_oracle_collision_count", 0) for batch in batches) == 0
            and doc.get("classification") in accepted
        ),
        "classification": doc.get("classification"),
        "points": [
            {
                "concurrency": batch["concurrency"],
                "aggregate_tok_s": batch["aggregate_tok_s_wall"],
                "per_user_tok_s": batch["aggregate_tok_s_wall"] / batch["concurrency"],
                "cached_tokens_all_zero": batch.get("cached_tokens_all_zero"),
            }
            for batch in batches
        ],
    }

zero_q = qualify_performance(zero)
two_q = qualify_performance(two)
draft_counter_unchanged = before == after_zero
draft_counter_increased = after_two > after_zero
qualified = (
    zero_q["qualified"]
    and two_q["qualified"]
    and canary.get("pass_all") is True
    and canary.get("speculative_n_max") == 0
    and all(
        row.get("cached_tokens_nonzero") == 0
        for row in canary.get("results", [])
    )
    and default_canary.get("pass_all") is True
    and draft_counter_unchanged
    and draft_counter_increased
)
result = {
    "qualified": qualified,
    "nmax0": zero_q,
    "nmax2": two_q,
    "nmax0_semantic_canary_pass": canary.get("pass_all"),
    "default_mtp2_canaries_pass": default_canary.get("pass_all"),
    "draft_tokens_before_nmax0": before,
    "draft_tokens_after_nmax0": after_zero,
    "draft_tokens_after_nmax2": after_two,
    "nmax0_draft_counter_unchanged": draft_counter_unchanged,
    "nmax2_draft_counter_increased": draft_counter_increased,
}
json.dump(result, open(root / "qualification.json", "w"), indent=2)
print(json.dumps(result, indent=2))
if not qualified:
    raise SystemExit(3)
PY
fi

printf 'PASS: %s\n' "${out_dir}"
