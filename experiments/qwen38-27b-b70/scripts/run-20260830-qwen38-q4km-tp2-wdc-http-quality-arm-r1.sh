#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
profile=${PROFILE:?set PROFILE to realistic or concurrency}
arm=${ARM:?set ARM to control or candidate}
attempt=${ATTEMPT:-1}
port=${PORT:-18154}
source_dir=${SOURCE_DIR:-/media/steve/extended-ssd/steve-archive/active-qwen38-tp1-concurrency-20260825}
build_dir=${BUILD_DIR:-${source_dir}/build-sycl-aot-bmg-g31-wdc-noq6-r5}
target_dir=${TARGET_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-gguf}
draft_dir=${DRAFT_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-unsloth-gguf/MTP}
out_parent=${OUT_DIR:-/mnt/fast-ai/bench-results}
campaign=qwen38-q4km-tp2-wdc-http-quality-20260830-r1
run_dir=${out_parent}/${campaign}-${profile}-${arm}-attempt${attempt}

target=${target_dir}/Qwen3.8-27B-Q4_K_M.gguf
server=${build_dir}/bin/llama-server
backend=${build_dir}/bin/libggml-sycl.so.0.19.0
server_impl=${build_dir}/bin/libllama-server-impl.so
launcher=${repo}/repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
prereg=${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-wdc-http-quality-r1-prereg.json
realistic_harness=${repo}/scripts/bench-openai-realistic-suite.py
realistic_suite=${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json
realistic_oracle=${repo}/experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-q4k-glu-summary.json
concurrency_harness=${repo}/scripts/bench-openai-concurrency-oracle.py
concurrency_qualifier=${repo}/scripts/qualify-openai-concurrency-attempt.py
concurrency_suite=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
concurrency_oracle=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-concurrency-oracle-digests.json

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
case ${profile} in realistic|concurrency) ;; *) fail 'PROFILE must be realistic or concurrency' ;; esac
case ${arm} in control) wdc=0 ;; candidate) wdc=1 ;; *) fail 'ARM must be control or candidate' ;; esac
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
[[ "$(findmnt -no FSTYPE --target "${out_parent}")" == ext4 ]] || fail 'OUT_DIR must be ext4'

check_hash() {
  local expected=$1 path=$2 actual
  [[ -f "${path}" ]] || fail "missing ${path}"
  actual=$(sha256sum "${path}" | awk '{print $1}')
  [[ "${actual}" == "${expected}" ]] || fail "identity mismatch: ${path}"
}
check_hash 31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34 "${target}"
check_hash 7983061d46a7fecf61b498fc159c11a5cfec5dc078ba0dbaa114b5b8c934cf2c "${server}"
check_hash 72beceb1906a130c3f5d064fb68a844b792ecdc28d3230935cdea9be259f4daf "${backend}"
check_hash fd649584afe51a708728bcb4da6b415d60b3c6cb8a6203f5d7ae38fb6272cc05 "${server_impl}"
check_hash ee0d3998adaac33405e3b5536bf6d7b7b04a014e37eedbd628b6968a23895f52 "${realistic_harness}"
check_hash df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac "${realistic_suite}"
check_hash f8e7e4040d653ef6250ed99362221f68a349ddb003f52769560b87877c0e34af "${realistic_oracle}"
check_hash 1ea05f6332e2153be408d2df126546705ea559b0364a368df297d58787e356d2 "${concurrency_harness}"
check_hash 9f2a50dbc5c5cdabfee742429fc3e2531044a262691e28e1a2da5469ba4696b1 "${concurrency_qualifier}"
check_hash 2136a875ef55c71454066e2509061eed11b7e0ccaf98a3e0866a6eabce1cfce4 "${concurrency_suite}"
check_hash 0a9095d3407263150fce9794035c33ed480a0ba04908f793ae6810d4e5567e33 "${concurrency_oracle}"
[[ -f "${prereg}" ]] || fail "missing ${prereg}"
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126 ]] || fail 'source commit mismatch'
[[ "$(git -C "${source_dir}" diff --binary | sha256sum | awk '{print $1}')" == 9cee85631ded5eca3dd4576100496f147468f69aa99e0df147f54c0f64f49926 ]] || fail 'source diff mismatch'

exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
pgrep -x llama-server >/dev/null && fail 'another llama-server is running'
mkdir -p "${run_dir}"
date -u +%Y-%m-%dT%H:%M:%SZ >"${run_dir}/start-utc.txt"
sha256sum "${target}" "${server}" "${backend}" "${server_impl}" "${launcher}" \
  "${prereg}" "${realistic_harness}" "${realistic_suite}" "${realistic_oracle}" \
  "${concurrency_harness}" "${concurrency_qualifier}" "${concurrency_suite}" \
  "${concurrency_oracle}" "${BASH_SOURCE[0]}" >"${run_dir}/input-sha256sums.txt"
git -C "${source_dir}" diff --binary >"${run_dir}/source.diff"
git -C "${source_dir}" status --short >"${run_dir}/source-status.txt"
free -b >"${run_dir}/memory-before.txt"
for device in 0 1; do
  xpu-smi dump --device "${device}" --metrics MEMORY,POWER --number 1 >"${run_dir}/xpu-before-${device}.txt" 2>&1 || true
done

if [[ "${profile}" == realistic ]]; then
  context=8192; parallel=1
else
  context=32768; parallel=64
fi

server_job=
cleanup() {
  set +e
  cleanup_status=clean
  pid=$(pgrep -n -x llama-server 2>/dev/null || true)
  if [[ -n "${pid}" ]]; then
    kill -INT "${pid}" 2>/dev/null
    for _ in $(seq 1 120); do kill -0 "${pid}" 2>/dev/null || break; sleep 0.5; done
    if kill -0 "${pid}" 2>/dev/null; then
      cleanup_status=escalated-term
      kill -TERM "${pid}" 2>/dev/null
      for _ in $(seq 1 60); do kill -0 "${pid}" 2>/dev/null || break; sleep 0.5; done
    fi
    kill -0 "${pid}" 2>/dev/null && cleanup_status=process-survived
  fi
  if [[ -n "${server_job}" ]] && kill -0 "${server_job}" 2>/dev/null; then wait "${server_job}" 2>/dev/null; fi
  printf '%s\n' "${cleanup_status}" >"${run_dir}/cleanup-status.txt"
  free -b >"${run_dir}/memory-after.txt" 2>/dev/null || true
  for device in 0 1; do
    xpu-smi dump --device "${device}" --metrics MEMORY,POWER --number 1 >"${run_dir}/xpu-after-${device}.txt" 2>&1 || true
  done
}
trap cleanup EXIT INT TERM

timeout --signal=INT --kill-after=30s 3600s env \
  TARGET_DIR="${target_dir}" DRAFT_DIR="${draft_dir}" BUILD_DIR="${build_dir}" \
  ALLOW_REBUILT_BINARIES=1 MTP_DEPTH=0 WDC_Q4K="${wdc}" PORT="${port}" \
  CTX_SIZE="${context}" PARALLEL_SLOTS="${parallel}" BATCH_SIZE=2048 \
  UBATCH_SIZE=256 THREADS=8 "${launcher}" >"${run_dir}/server.log" 2>&1 &
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
tr '\0' ' ' <"/proc/${pid}/cmdline" >"${run_dir}/server-command.txt"; printf '\n' >>"${run_dir}/server-command.txt"
tr '\0' '\n' <"/proc/${pid}/environ" | \
  grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|ONEAPI_ROOT=|LD_LIBRARY_PATH=)' | sort >"${run_dir}/runtime-environment.txt"
curl -fsS "http://127.0.0.1:${port}/props" >"${run_dir}/props.json"
curl -fsS "http://127.0.0.1:${port}/slots" >"${run_dir}/slots-before.json"

if [[ "${profile}" == realistic ]]; then
  python3 "${realistic_harness}" \
    --base-url "http://127.0.0.1:${port}" --model "qwen38-q4km-tp2-wdc-${arm}" \
    --api-mode completions --suite "${realistic_suite}" --max-tokens 512 \
    --metric-tokens 100 --seed 1 --timeout 900 --require-natural-eos \
    --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0}' \
    --out "${run_dir}/result.json" | tee "${run_dir}/harness-summary.txt"
  python3 - "${run_dir}" "${realistic_oracle}" "${arm}" <<'PY'
import json, pathlib, sys
root, oracle_path, arm = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
result = json.loads((root / "result.json").read_text())
oracle = json.loads(oracle_path.read_text())
gate = result["realistic_final_gate"]
fresh = result["fresh_response_validity"]
exact = result["output_sha256s"] == oracle["output_sha256s"]
summary = {
    "profile": "realistic",
    "arm": arm,
    "quality_qualified": bool(gate.get("passed") and fresh.get("valid") and exact),
    "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
    "output_hashes_exact": exact,
    "output_hash_count": len(result["output_sha256s"]),
    "median_tok_s_1_100_after_ttft": result["summary"]["tok_s_1_100_after_ttft"]["median"],
    "median_tok_s_after_ttft_full": result["summary"]["tok_s_after_ttft_full"]["median"],
    "median_ttft_ms": result["summary"]["ttft_ms"]["median"],
}
(root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
if not summary["quality_qualified"]: raise SystemExit(3)
PY
else
  python3 "${concurrency_harness}" \
    --base-url "http://127.0.0.1:${port}" --model "qwen38-q4km-tp2-wdc-${arm}" \
    --api-mode native --suite "${concurrency_suite}" --concurrency 64 --repeats 1 \
    --max-tokens 128 --seed 42 --timeout 1200 --return-token-ids \
    --oracle-digests "${concurrency_oracle}" \
    --request-id-prefix "qwen38-q4km-tp2-wdc-${arm}-a${attempt}" \
    --request-extra-json '{"cache_prompt":false,"ignore_eos":true,"temperature":0}' \
    --out "${run_dir}/result.json" | tee "${run_dir}/harness-summary.txt"
  python3 "${concurrency_qualifier}" --result "${run_dir}/result.json" \
    --out "${run_dir}/qualification.json" --active-slots 64
  python3 - "${run_dir}" "${arm}" <<'PY'
import json, pathlib, sys
root, arm = pathlib.Path(sys.argv[1]), sys.argv[2]
result = json.loads((root / "result.json").read_text())
quality = json.loads((root / "qualification.json").read_text())
summary = {
    "profile": "concurrency",
    "arm": arm,
    "quality_qualified": quality.get("batch_gates_passed") is True,
    "aggregate_tok_s_c64": result["batches"][0]["aggregate_tok_s_wall"],
    "cached_tokens_all_zero": quality.get("cached_tokens_all_zero"),
    "complete_token_id_identity_all": quality.get("complete_token_id_identity_all"),
    "cross_base_oracle_collision_count": quality.get("cross_base_oracle_collision_count"),
}
(root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
if not summary["quality_qualified"]: raise SystemExit(3)
PY
fi

curl -fsS "http://127.0.0.1:${port}/slots" >"${run_dir}/slots-after.json"
start=$(cat "${run_dir}/start-utc.txt")
journalctl -k -b --since "${start}" --no-pager | \
  grep -Ei 'llama-server.*segfault|xe.*(fault|reset|hang)|device lost|CAT fault|oom|out of memory' \
  >"${run_dir}/kernel-errors.txt" || true
[[ ! -s "${run_dir}/kernel-errors.txt" ]] || fail 'kernel error evidence found'
engaged=0; grep -q 'weight-decompression GEMM ENGAGED' "${run_dir}/server.log" && engaged=1
if [[ "${profile}" == concurrency && "${arm}" == candidate && "${engaged}" != 1 ]]; then fail 'candidate WDC liveness failed'; fi
if [[ "${arm}" == control && "${engaged}" != 0 ]]; then fail 'control WDC negative control failed'; fi
printf '%s\n' "${engaged}" >"${run_dir}/wdc-engaged.txt"
sha256sum "${run_dir}/result.json" "${run_dir}/summary.json" >"${run_dir}/result-sha256sums.txt"
printf 'PASS: %s\n' "${run_dir}"
