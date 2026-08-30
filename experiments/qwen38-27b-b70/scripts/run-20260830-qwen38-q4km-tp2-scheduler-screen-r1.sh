#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
arm=${ARM:?set ARM to a frozen preregistered arm}
attempt=${ATTEMPT:-1}
port=${PORT:-18149}
target_dir=${TARGET_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-gguf}
draft_dir=${DRAFT_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-unsloth-gguf/MTP}
source_dir=${SOURCE_DIR:-/mnt/fast-ai/build/qwen38-q4mtp-request-spec-nmax-r1-src}
build_dir=${BUILD_DIR:-${source_dir}/build-sycl-aot-bmg-g31-oneapi2026.1.1}
out_parent=${OUT_DIR:-/mnt/fast-ai/bench-results}
campaign=qwen38-q4km-tp2-scheduler-screen-20260830-r1

case ${arm} in
  b1024-u256-c32768-t8)  batch=1024; ubatch=256; context=32768; threads=8 ;;
  b2048-u256-c32768-t8)  batch=2048; ubatch=256; context=32768; threads=8 ;;
  b4096-u256-c32768-t8)  batch=4096; ubatch=256; context=32768; threads=8 ;;
  b2048-u512-c32768-t8)  batch=2048; ubatch=512; context=32768; threads=8 ;;
  b2048-u256-c16384-t8)  batch=2048; ubatch=256; context=16384; threads=8 ;;
  b2048-u256-c32768-t16) batch=2048; ubatch=256; context=32768; threads=16 ;;
  *) printf 'FAIL: unsupported frozen arm: %s\n' "${arm}" >&2; exit 2 ;;
esac

run_dir=${out_parent}/${campaign}-${arm}-attempt${attempt}
target=${target_dir}/Qwen3.8-27B-Q4_K_M.gguf
draft=${draft_dir}/mtp-Qwen3.8-27B-Q4_0.gguf
server=${build_dir}/bin/llama-server
backend=${build_dir}/bin/libggml-sycl.so
server_impl=${build_dir}/bin/libllama-server-impl.so
launcher=${repo}/repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
suite=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
oracle=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-concurrency-oracle-digests.json
prereg=${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-scheduler-screen-r1-prereg.json
harness=${repo}/scripts/bench-openai-concurrency-oracle.py
qualifier=${repo}/scripts/qualify-openai-concurrency-attempt.py
candidate_patch=${repo}/experiments/qwen38-27b-b70/patches/llama-cpp-request-spec-nmax-candidate-20260830.patch

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
[[ "$(findmnt -no FSTYPE --target "${out_parent}")" == ext4 ]] || fail 'OUT_DIR must be on ext4'

check_hash() {
  local expected=$1 path=$2 actual
  [[ -f "${path}" ]] || fail "missing ${path}"
  actual=$(sha256sum "${path}" | awk '{print $1}')
  [[ "${actual}" == "${expected}" ]] || fail "identity mismatch: ${path}"
}

check_hash 31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34 "${target}"
check_hash 50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e "${draft}"
check_hash 408e3b3cc1e4f48e5d955d5acf72444e0f1ddfaf5802c19f3d69b181bb8eecb9 "${server}"
check_hash 256312e871752d4ba3af09704843eb08efbd46e35d42ee04dfe4ec81d17e687f "${backend}"
check_hash c8c0e5d701445f6f8ca43f3cc0dfcfd6de5d70b2314b77d3bdf88ace6e6314fb "${server_impl}"
check_hash 4091ebd53fcae8dd952a3b8f96b5df2248e2d363d92ff7350694df56be6fbdc3 "${candidate_patch}"
check_hash 2136a875ef55c71454066e2509061eed11b7e0ccaf98a3e0866a6eabce1cfce4 "${suite}"
check_hash 0a9095d3407263150fce9794035c33ed480a0ba04908f793ae6810d4e5567e33 "${oracle}"
check_hash 1ea05f6332e2153be408d2df126546705ea559b0364a368df297d58787e356d2 "${harness}"
check_hash 9f2a50dbc5c5cdabfee742429fc3e2531044a262691e28e1a2da5469ba4696b1 "${qualifier}"
[[ -f "${prereg}" ]] || fail "missing ${prereg}"
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126 ]] || fail 'source commit mismatch'
[[ "$(git -C "${source_dir}" diff --binary | sha256sum | awk '{print $1}')" == 0e791be3b5a66bcd37e0bcf4b905ef609c4456c2cb5e5b8b6d12123f15af6864 ]] || fail 'source diff mismatch'

exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'
mkdir -p "${run_dir}"

sha256sum "${target}" "${draft}" "${server}" "${backend}" "${server_impl}" \
  "${candidate_patch}" "${suite}" "${oracle}" "${harness}" "${qualifier}" \
  "${prereg}" "${launcher}" "${BASH_SOURCE[0]}" >"${run_dir}/input-sha256sums.txt"
git -C "${source_dir}" diff --binary >"${run_dir}/source.diff"
git -C "${source_dir}" status --short >"${run_dir}/source-status.txt"
free -b >"${run_dir}/memory-before.txt"
xpu-smi dump --device 0,1 --metrics MEMORY,POWER --number 1 >"${run_dir}/xpu-before.txt" 2>&1 || true

server_job=
cleanup() {
  set +e
  cleanup_status=clean
  pid=$(pgrep -n -x llama-server 2>/dev/null || true)
  if [[ -n "${pid}" ]]; then
    # Signal the server exactly once. Signalling the outer timeout first and
    # then the server raced two interrupts through llama.cpp teardown and made
    # otherwise complete diagnostics segfault after their results were saved.
    kill -INT "${pid}" 2>/dev/null
    for _ in $(seq 1 120); do kill -0 "${pid}" 2>/dev/null || break; sleep 0.5; done
    if kill -0 "${pid}" 2>/dev/null; then
      cleanup_status=escalated-term
      kill -TERM "${pid}" 2>/dev/null
      for _ in $(seq 1 60); do kill -0 "${pid}" 2>/dev/null || break; sleep 0.5; done
    fi
    kill -0 "${pid}" 2>/dev/null && cleanup_status=process-survived
  fi
  if [[ -n "${server_job}" ]] && kill -0 "${server_job}" 2>/dev/null; then
    wait "${server_job}" 2>/dev/null
  fi
  printf '%s\n' "${cleanup_status}" >"${run_dir}/cleanup-status.txt"
  free -b >"${run_dir}/memory-after.txt" 2>/dev/null || true
  xpu-smi dump --device 0,1 --metrics MEMORY,POWER --number 1 >"${run_dir}/xpu-after.txt" 2>&1 || true
}
trap cleanup EXIT INT TERM

timeout --signal=INT --kill-after=30s 3600s env \
  TARGET_DIR="${target_dir}" DRAFT_DIR="${draft_dir}" BUILD_DIR="${build_dir}" \
  ALLOW_REBUILT_BINARIES=1 MTP_DEPTH=0 PORT="${port}" \
  CTX_SIZE="${context}" PARALLEL_SLOTS=64 BATCH_SIZE="${batch}" \
  UBATCH_SIZE="${ubatch}" THREADS="${threads}" \
  "${launcher}" >"${run_dir}/server.log" 2>&1 &
server_job=$!

healthy=0
for _ in $(seq 1 600); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${run_dir}/health.json" 2>/dev/null; then healthy=1; break; fi
  kill -0 "${server_job}" 2>/dev/null || break
  sleep 1
done
(( healthy == 1 )) || fail 'server did not become healthy'

pid=$(pgrep -n -x llama-server || true)
[[ -n "${pid}" ]] || fail 'healthy endpoint has no llama-server process'
tr '\0' ' ' <"/proc/${pid}/cmdline" >"${run_dir}/server-command.txt"
printf '\n' >>"${run_dir}/server-command.txt"
tr '\0' '\n' <"/proc/${pid}/environ" |
  grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|SYCL_UR_USE_LEVEL_ZERO_V2=|ONEAPI_ROOT=|LD_LIBRARY_PATH=)' |
  LC_ALL=C sort >"${run_dir}/runtime-environment.txt"
curl -fsS "http://127.0.0.1:${port}/props" >"${run_dir}/props.json"
curl -fsS "http://127.0.0.1:${port}/slots" >"${run_dir}/slots-before.json"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${run_dir}/metrics-before.txt"

python3 "${harness}" \
  --base-url "http://127.0.0.1:${port}" \
  --model "qwen38-q4km-tp2-scheduler-${arm}" --api-mode native \
  --suite "${suite}" --concurrency 64 --repeats 1 --max-tokens 128 \
  --seed 42 --timeout 1200 --return-token-ids --oracle-digests "${oracle}" \
  --request-id-prefix "qwen38-q4km-tp2-scheduler-${arm}" \
  --request-extra-json '{"cache_prompt":false,"ignore_eos":true,"temperature":0}' \
  --out "${run_dir}/result.json" | tee "${run_dir}/harness-summary.txt"

python3 "${qualifier}" --result "${run_dir}/result.json" \
  --out "${run_dir}/qualification.json" --active-slots 64
curl -fsS "http://127.0.0.1:${port}/metrics" >"${run_dir}/metrics-after.txt"
curl -fsS "http://127.0.0.1:${port}/slots" >"${run_dir}/slots-after.json"
sha256sum "${run_dir}/result.json" "${run_dir}/qualification.json" >"${run_dir}/result-sha256sums.txt"

python3 - "${run_dir}" "${arm}" "${batch}" "${ubatch}" "${context}" "${threads}" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
arm, batch, ubatch, context, threads = sys.argv[2:]
result = json.load(open(root / "result.json"))
qualification = json.load(open(root / "qualification.json"))
rate = result["batches"][0]["aggregate_tok_s_wall"]
summary = {
    "arm": arm,
    "batch_size": int(batch),
    "ubatch_size": int(ubatch),
    "total_context": int(context),
    "threads": int(threads),
    "aggregate_tok_s_c64": rate,
    "qualified": qualification.get("batch_gates_passed") is True,
    "classification": qualification.get("classification"),
    "cached_tokens_all_zero": qualification.get("cached_tokens_all_zero"),
    "complete_token_id_identity_all": qualification.get("complete_token_id_identity_all"),
    "cross_base_oracle_collision_count": qualification.get("cross_base_oracle_collision_count"),
}
json.dump(summary, open(root / "screen-summary.json", "w"), indent=2)
print(json.dumps(summary, indent=2))
if not summary["qualified"]:
    raise SystemExit(3)
PY

printf 'PASS: %s\n' "${run_dir}"
