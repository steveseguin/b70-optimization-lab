#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
target_dir=${TARGET_DIR:?set TARGET_DIR}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR}
build_dir=${BUILD_DIR:?set BUILD_DIR}
arm=${ARM:?set ARM to explicit-default, default-explicit, or pre-stress-post}
out_dir=${OUT_DIR:?set OUT_DIR to a new directory}
port=${PORT:-18148}
prereg=${PREREG:-${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4mtp-request-nmax-order-r1-prereg.json}
launcher=${repo}/repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
harness=${repo}/scripts/bench-openai-concurrency-oracle.py
suite=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
oracle=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-concurrency-oracle-digests.json
target=${target_dir}/Qwen3.8-27B-Q4_K_M.gguf
draft=${draft_dir}/mtp-Qwen3.8-27B-Q4_0.gguf
server=${build_dir}/bin/llama-server
backend=${build_dir}/bin/libggml-sycl.so
server_impl=${build_dir}/bin/libllama-server-impl.so

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
case ${arm} in explicit-default|default-explicit|pre-stress-post) ;; *) fail 'invalid ARM' ;; esac
[[ ! -e "${out_dir}" ]] || fail "refusing to overwrite ${out_dir}"
for path in "${prereg}" "${launcher}" "${harness}" "${suite}" "${oracle}"; do
  [[ -f "${path}" ]] || fail "missing ${path}"
done

check_hash() {
  local expected=$1 path=$2
  [[ "$(sha256sum "${path}" | awk '{print $1}')" == "${expected}" ]] || fail "identity mismatch: ${path}"
}
check_hash 31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34 "${target}"
check_hash 50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e "${draft}"
check_hash 408e3b3cc1e4f48e5d955d5acf72444e0f1ddfaf5802c19f3d69b181bb8eecb9 "${server}"
check_hash 256312e871752d4ba3af09704843eb08efbd46e35d42ee04dfe4ec81d17e687f "${backend}"
check_hash c8c0e5d701445f6f8ca43f3cc0dfcfd6de5d70b2314b77d3bdf88ace6e6314fb "${server_impl}"

exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
pgrep -x llama-server >/dev/null && fail 'another llama-server is running'
mkdir -p "${out_dir}"
sha256sum "${target}" "${draft}" "${server}" "${backend}" "${server_impl}" \
  "${prereg}" "${launcher}" "${harness}" "${suite}" "${oracle}" >"${out_dir}/sha256sums.txt"
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
  [[ -z "${pid}" ]] || kill -TERM "${pid}" 2>/dev/null || true
  free -b >"${out_dir}/memory-after.txt" 2>/dev/null || true
  xpu-smi dump --device 0,1 --metrics MEMORY,POWER --number 1 >"${out_dir}/xpu-after.txt" 2>&1 || true
}
trap cleanup EXIT INT TERM

timeout --signal=INT --kill-after=30s 3600s env \
  TARGET_DIR="${target_dir}" DRAFT_DIR="${draft_dir}" BUILD_DIR="${build_dir}" \
  ALLOW_REBUILT_BINARIES=1 MTP_DEPTH=2 PORT="${port}" CTX_SIZE=32768 PARALLEL_SLOTS=64 \
  BATCH_SIZE=1024 UBATCH_SIZE=256 THREADS=8 "${launcher}" >"${out_dir}/server.log" 2>&1 &
server_job=$!
healthy=0
for _ in $(seq 1 600); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/health.json" 2>/dev/null; then
    healthy=1
    break
  fi
  kill -0 "${server_job}" 2>/dev/null || break
  sleep 1
done
(( healthy == 1 )) || fail 'server did not become healthy'
pid=$(pgrep -n -x llama-server || true)
[[ -n "${pid}" ]] || fail 'healthy endpoint has no llama-server process'
tr '\0' ' ' <"/proc/${pid}/cmdline" >"${out_dir}/server-command.txt"; printf '\n' >>"${out_dir}/server-command.txt"
tr '\0' '\n' <"/proc/${pid}/environ" |
  grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|ONEAPI_ROOT=|LD_LIBRARY_PATH=)' |
  LC_ALL=C sort >"${out_dir}/runtime-environment.txt"

run_low() {
  local label=$1 extra=$2
  python3 "${harness}" --base-url "http://127.0.0.1:${port}" \
    --model "qwen38-request-order-${arm}-${label}" --api-mode native --suite "${suite}" \
    --concurrency 1,2 --repeats 1 --max-tokens 128 --seed 42 --timeout 900 \
    --return-token-ids --oracle-digests "${oracle}" \
    --request-id-prefix "qwen38-request-order-${arm}-${label}" \
    --request-extra-json "${extra}" --out "${out_dir}/${label}.json" |
    tee "${out_dir}/${label}.stdout"
}

explicit='{"cache_prompt":false,"ignore_eos":true,"temperature":0,"speculative.n_max":2}'
default='{"cache_prompt":false,"ignore_eos":true,"temperature":0}'
zero='{"cache_prompt":false,"ignore_eos":true,"temperature":0,"speculative.n_max":0}'

case ${arm} in
  explicit-default)
    run_low explicit-first "${explicit}"
    run_low default-second "${default}"
    ;;
  default-explicit)
    run_low default-first "${default}"
    run_low explicit-second "${explicit}"
    ;;
  pre-stress-post)
    run_low default-pre "${default}"
    python3 "${harness}" --base-url "http://127.0.0.1:${port}" \
      --model qwen38-request-order-stress-nmax0 --api-mode native --suite "${suite}" \
      --concurrency 64 --repeats 1 --max-tokens 128 --seed 42 --timeout 900 \
      --return-token-ids --oracle-digests "${oracle}" \
      --request-id-prefix qwen38-request-order-stress-nmax0 \
      --request-extra-json "${zero}" --out "${out_dir}/nmax0-stress.json" |
      tee "${out_dir}/nmax0-stress.stdout"
    run_low default-post "${default}"
    ;;
esac

curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-after.txt"
curl -fsS "http://127.0.0.1:${port}/slots" >"${out_dir}/slots-after.json"
python3 - "${out_dir}" "${arm}" <<'PY'
import json, pathlib, sys
root, arm = pathlib.Path(sys.argv[1]), sys.argv[2]
paths = sorted(root.glob("*.json"))
documents = {}
for path in paths:
    if path.name in {"health.json", "slots-after.json"}:
        continue
    doc = json.load(open(path))
    if "batches" not in doc:
        continue
    batches = doc["batches"]
    rows = [row for batch in batches for row in batch["rows"]]
    qualified = (
        all(row.get("completion_tokens") == 128 for row in rows)
        and all(batch.get("cached_tokens_all_zero") for batch in batches)
        and all(batch.get("complete_token_id_identity_all") for batch in batches)
        and sum(batch.get("cross_base_oracle_collision_count", 0) for batch in batches) == 0
        and doc.get("classification") in {
            "output-identity-qualified",
            "output-isolation-qualified-shape-variant",
        }
    )
    documents[path.stem] = {
        "qualified": qualified,
        "classification": doc.get("classification"),
        "points": {str(b["concurrency"]): b["aggregate_tok_s_wall"] for b in batches},
    }
result = {
    "arm": arm,
    "qualified": bool(documents) and all(d["qualified"] for d in documents.values()),
    "documents": documents,
    "promotion_authorized": False,
}
json.dump(result, open(root / "qualification.json", "w"), indent=2)
print(json.dumps(result, indent=2))
if not result["qualified"]:
    raise SystemExit(3)
PY
printf 'PASS: %s\n' "${out_dir}"
