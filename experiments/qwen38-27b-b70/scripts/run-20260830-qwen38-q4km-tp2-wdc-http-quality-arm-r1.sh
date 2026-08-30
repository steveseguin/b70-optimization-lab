#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
profile=${PROFILE:?set PROFILE to realistic or concurrency}
arm=${ARM:?set ARM to control or candidate}
attempt=${ATTEMPT:-1}
baseline_mode=${BASELINE_MODE:-0}
pilot_mode=${PILOT_MODE:-0}
q4k_reorder=${Q4K_REORDER:-1}
batch_size=${BATCH_SIZE:-2048}
queue_settle_ms=${QUEUE_SETTLE_MS:-0}
mtp_depth=${MTP_DEPTH:-0}
tp_size=${TP_SIZE:-2}
concurrency=${CONCURRENCY:-64}
context_override=${CONTEXT_SIZE:-}
feature_profile=${FEATURE_PROFILE:-tuned}
q8_dedup_override=${Q8_DEDUP_OVERRIDE:-}
launch_stagger_ms=${LAUNCH_STAGGER_MS:-0}
pin_slots=${PIN_SLOTS:-0}
wdc_q4k_name_filter=${WDC_Q4K_NAME_FILTER:-}
candidate_kind=${CANDIDATE_KIND:-wdc}
q4k_f16_cache_filter=${Q4K_F16_CACHE_FILTER:-}
port=${PORT:-18154}
source_dir=${SOURCE_DIR:-/media/steve/extended-ssd/steve-archive/active-qwen38-tp1-concurrency-20260825}
build_dir=${BUILD_DIR:-${source_dir}/build-sycl-aot-bmg-g31-wdc-noq6-r5}
target_dir=${TARGET_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-gguf}
draft_dir=${DRAFT_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-unsloth-gguf/MTP}
out_parent=${OUT_DIR:-/mnt/fast-ai/bench-results}
campaign=${CAMPAIGN:-qwen38-q4km-tp2-wdc-http-quality-20260830-r1}
run_dir=${out_parent}/${campaign}-${profile}-${arm}-attempt${attempt}

target=${target_dir}/Qwen3.8-27B-Q4_K_M.gguf
server=${build_dir}/bin/llama-server
backend=${build_dir}/bin/libggml-sycl.so.0.19.0
server_impl=${build_dir}/bin/libllama-server-impl.so
launcher=${repo}/repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/run-server.sh
prereg=${PREREG:-${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-wdc-http-quality-r1-prereg.json}
realistic_harness=${repo}/scripts/bench-openai-realistic-suite.py
realistic_suite=${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json
realistic_oracle=${REALISTIC_ORACLE:-${repo}/experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-q4k-glu-summary.json}
concurrency_harness=${repo}/scripts/bench-openai-concurrency-oracle.py
concurrency_qualifier=${repo}/scripts/qualify-openai-concurrency-attempt.py
concurrency_suite=${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
concurrency_oracle=${CONCURRENCY_ORACLE:-${repo}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-concurrency-oracle-digests.json}
expected_realistic_oracle_sha256=${EXPECTED_REALISTIC_ORACLE_SHA256:-f8e7e4040d653ef6250ed99362221f68a349ddb003f52769560b87877c0e34af}
expected_concurrency_oracle_sha256=${EXPECTED_CONCURRENCY_ORACLE_SHA256:-0a9095d3407263150fce9794035c33ed480a0ba04908f793ae6810d4e5567e33}
expected_server_sha256=${EXPECTED_SERVER_SHA256:-7983061d46a7fecf61b498fc159c11a5cfec5dc078ba0dbaa114b5b8c934cf2c}
expected_backend_sha256=${EXPECTED_BACKEND_SHA256:-72beceb1906a130c3f5d064fb68a844b792ecdc28d3230935cdea9be259f4daf}
expected_server_impl_sha256=${EXPECTED_SERVER_IMPL_SHA256:-fd649584afe51a708728bcb4da6b415d60b3c6cb8a6203f5d7ae38fb6272cc05}
expected_source_diff_sha256=${EXPECTED_SOURCE_DIFF_SHA256:-9cee85631ded5eca3dd4576100496f147468f69aa99e0df147f54c0f64f49926}
expected_concurrency_harness_sha256=${EXPECTED_CONCURRENCY_HARNESS_SHA256:-1ea05f6332e2153be408d2df126546705ea559b0364a368df297d58787e356d2}
expected_concurrency_qualifier_sha256=${EXPECTED_CONCURRENCY_QUALIFIER_SHA256:-9f2a50dbc5c5cdabfee742429fc3e2531044a262691e28e1a2da5469ba4696b1}

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
case ${profile} in realistic|concurrency) ;; *) fail 'PROFILE must be realistic or concurrency' ;; esac
case ${candidate_kind} in wdc|q4k-f16-cache) ;; *) fail 'CANDIDATE_KIND must be wdc or q4k-f16-cache' ;; esac
case ${arm} in
  control) wdc=0 ;;
  candidate) [[ "${candidate_kind}" == wdc ]] && wdc=1 || wdc=0 ;;
  *) fail 'ARM must be control or candidate' ;;
esac
[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail 'ATTEMPT must be positive'
[[ "${baseline_mode}" == 0 || "${baseline_mode}" == 1 ]] || fail 'BASELINE_MODE must be 0 or 1'
[[ "${pilot_mode}" == 0 || "${pilot_mode}" == 1 ]] || fail 'PILOT_MODE must be 0 or 1'
[[ "${baseline_mode}" == 0 || "${arm}" == control ]] || fail 'BASELINE_MODE is control-only'
[[ "${pilot_mode}" == 0 || "${arm}" == control ]] || fail 'PILOT_MODE is control-only'
[[ "${pilot_mode}" == 0 || "${profile}" == concurrency ]] || fail 'PILOT_MODE is concurrency-only'
[[ "${baseline_mode}" == 0 || "${pilot_mode}" == 0 ]] || fail 'BASELINE_MODE and PILOT_MODE are mutually exclusive'
[[ "${q4k_reorder}" == 0 || "${q4k_reorder}" == 1 ]] || fail 'Q4K_REORDER must be 0 or 1'
[[ "${arm}" == control || "${q4k_reorder}" == 1 ]] || fail 'candidate requires Q4K_REORDER=1'
[[ "${batch_size}" =~ ^[1-9][0-9]*$ ]] || fail 'BATCH_SIZE must be positive'
[[ "${queue_settle_ms}" =~ ^[0-9]+$ ]] && (( queue_settle_ms <= 5000 )) || fail 'QUEUE_SETTLE_MS must be 0..5000'
[[ "${mtp_depth}" == 0 || "${mtp_depth}" == 2 ]] || fail 'MTP_DEPTH must be 0 or 2'
[[ "${tp_size}" == 1 || "${tp_size}" == 2 ]] || fail 'TP_SIZE must be 1 or 2'
[[ "${concurrency}" =~ ^[1-9][0-9]*$ ]] || fail 'CONCURRENCY must be positive'
[[ -z "${context_override}" || "${context_override}" =~ ^[1-9][0-9]*$ ]] || fail 'CONTEXT_SIZE must be positive'
[[ "${feature_profile}" == tuned || "${feature_profile}" == reference || "${feature_profile}" == base ]] || fail 'FEATURE_PROFILE must be tuned, reference, or base'
[[ "${feature_profile}" == tuned || "${arm}" == control ]] || fail 'non-tuned FEATURE_PROFILE is control-only'
[[ -z "${q8_dedup_override}" || "${q8_dedup_override}" == 0 || "${q8_dedup_override}" == 1 || "${q8_dedup_override}" == 2 ]] || fail 'Q8_DEDUP_OVERRIDE must be empty, 0, 1, or 2'
[[ "${launch_stagger_ms}" =~ ^[0-9]+$ ]] || fail 'LAUNCH_STAGGER_MS must be a nonnegative integer'
[[ "${pin_slots}" == 0 || "${pin_slots}" == 1 ]] || fail 'PIN_SLOTS must be 0 or 1'
[[ "${wdc_q4k_name_filter}" =~ ^[A-Za-z0-9_.,-]*$ ]] || fail 'WDC_Q4K_NAME_FILTER contains unsupported characters'
[[ -z "${wdc_q4k_name_filter}" || "${arm}" == candidate ]] || fail 'WDC_Q4K_NAME_FILTER is candidate-only'
[[ "${q4k_f16_cache_filter}" =~ ^[A-Za-z0-9_.,-]*$ ]] || fail 'Q4K_F16_CACHE_FILTER contains unsupported characters'
[[ -z "${q4k_f16_cache_filter}" || "${arm}" == candidate ]] || fail 'Q4K_F16_CACHE_FILTER is candidate-only'
[[ -z "${q4k_f16_cache_filter}" || "${candidate_kind}" == q4k-f16-cache ]] || fail 'Q4K_F16_CACHE_FILTER requires CANDIDATE_KIND=q4k-f16-cache'
[[ "${candidate_kind}" != q4k-f16-cache || "${arm}" == control || -n "${q4k_f16_cache_filter}" ]] || fail 'q4k-f16-cache candidate requires Q4K_F16_CACHE_FILTER'
[[ "${candidate_kind}" != q4k-f16-cache || -z "${wdc_q4k_name_filter}" ]] || fail 'cache candidate cannot set WDC_Q4K_NAME_FILTER'
if [[ "${profile}" == concurrency && "${queue_settle_ms}" != 0 ]]; then
  (( concurrency <= 1 || launch_stagger_ms * (concurrency - 1) < queue_settle_ms )) || fail 'launch stagger span must be shorter than queue settle window'
fi
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
[[ "$(findmnt -no FSTYPE --target "${out_parent}")" == ext4 ]] || fail 'OUT_DIR must be ext4'

check_hash() {
  local expected=$1 path=$2 actual
  [[ -f "${path}" ]] || fail "missing ${path}"
  actual=$(sha256sum "${path}" | awk '{print $1}')
  [[ "${actual}" == "${expected}" ]] || fail "identity mismatch: ${path}"
}
check_hash 31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34 "${target}"
check_hash "${expected_server_sha256}" "${server}"
check_hash "${expected_backend_sha256}" "${backend}"
check_hash "${expected_server_impl_sha256}" "${server_impl}"
check_hash ee0d3998adaac33405e3b5536bf6d7b7b04a014e37eedbd628b6968a23895f52 "${realistic_harness}"
check_hash df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac "${realistic_suite}"
check_hash "${expected_realistic_oracle_sha256}" "${realistic_oracle}"
check_hash "${expected_concurrency_harness_sha256}" "${concurrency_harness}"
check_hash "${expected_concurrency_qualifier_sha256}" "${concurrency_qualifier}"
check_hash 2136a875ef55c71454066e2509061eed11b7e0ccaf98a3e0866a6eabce1cfce4 "${concurrency_suite}"
check_hash "${expected_concurrency_oracle_sha256}" "${concurrency_oracle}"
[[ -f "${prereg}" ]] || fail "missing ${prereg}"
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126 ]] || fail 'source commit mismatch'
[[ "$(git -C "${source_dir}" diff --binary | sha256sum | awk '{print $1}')" == "${expected_source_diff_sha256}" ]] || fail 'source diff mismatch'

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
  context=${context_override:-32768}; parallel=${concurrency}
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
  ALLOW_REBUILT_BINARIES=1 MTP_DEPTH="${mtp_depth}" WDC_Q4K="${wdc}" Q4K_REORDER="${q4k_reorder}" PORT="${port}" \
  WDC_Q4K_NAME_FILTER="${wdc_q4k_name_filter}" \
  Q4K_F16_CACHE_FILTER="${q4k_f16_cache_filter}" \
  TP_SIZE="${tp_size}" \
  FEATURE_PROFILE="${feature_profile}" \
  Q8_DEDUP_OVERRIDE="${q8_dedup_override}" \
  CTX_SIZE="${context}" PARALLEL_SLOTS="${parallel}" BATCH_SIZE="${batch_size}" \
  QUEUE_SETTLE_MS="${queue_settle_ms}" \
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
  grep -E '^(GGML_|LLAMA_SERVER_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|ONEAPI_ROOT=|LD_LIBRARY_PATH=)' | sort >"${run_dir}/runtime-environment.txt"
curl -fsS "http://127.0.0.1:${port}/props" >"${run_dir}/props.json"
curl -fsS "http://127.0.0.1:${port}/slots" >"${run_dir}/slots-before.json"

if [[ "${profile}" == realistic ]]; then
  python3 "${realistic_harness}" \
    --base-url "http://127.0.0.1:${port}" --model "qwen38-q4km-tp2-wdc-${arm}" \
    --api-mode completions --suite "${realistic_suite}" --max-tokens 512 \
    --metric-tokens 100 --seed 1 --timeout 900 --require-natural-eos \
    --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0}' \
    --out "${run_dir}/result.json" | tee "${run_dir}/harness-summary.txt"
  python3 - "${run_dir}" "${realistic_oracle}" "${arm}" "${baseline_mode}" <<'PY'
import json, pathlib, sys
root, oracle_path, arm = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
baseline_mode = sys.argv[4] == "1"
result = json.loads((root / "result.json").read_text())
oracle = json.loads(oracle_path.read_text())
gate = result["realistic_final_gate"]
fresh = result["fresh_response_validity"]
exact = result["output_sha256s"] == oracle["output_sha256s"]
summary = {
    "profile": "realistic",
    "arm": arm,
    "baseline_generation": baseline_mode,
    "quality_qualified": bool(gate.get("passed") and fresh.get("valid") and (baseline_mode or exact)),
    "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
    "output_hashes_exact": exact,
    "output_hash_count": len(result["output_sha256s"]),
    "median_tok_s_1_100_after_ttft": result["summary"]["tok_s_1_100_after_ttft"]["median"],
    "median_tok_s_after_ttft_full": result["summary"]["tok_s_after_ttft_full"]["median"],
    "median_ttft_ms": result["summary"]["ttft_ms"]["median"],
}
(root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
if baseline_mode:
    baseline = {
        "schema": "neural.download.realistic-output-oracle.v1",
        "source_result_sha256": __import__("hashlib").sha256((root / "result.json").read_bytes()).hexdigest(),
        "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
        "output_sha256s": result["output_sha256s"],
    }
    (root / "realistic-oracle.json").write_text(json.dumps(baseline, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY
else
  harness_cmd=(python3 "${concurrency_harness}"
    --base-url "http://127.0.0.1:${port}" --model "qwen38-q4km-tp2-wdc-${arm}"
    --api-mode native --suite "${concurrency_suite}" --concurrency "${concurrency}" --repeats 1
    --max-tokens 128 --seed 42 --timeout 1200 --return-token-ids
    --launch-stagger-ms "${launch_stagger_ms}"
    --request-id-prefix "qwen38-q4km-tp2-wdc-${arm}-a${attempt}"
    --request-extra-json '{"cache_prompt":false,"ignore_eos":true,"temperature":0}'
    --out "${run_dir}/result.json")
  if [[ "${pin_slots}" == 1 ]]; then harness_cmd+=(--pin-slots); fi
  if [[ "${baseline_mode}" == 0 ]]; then harness_cmd+=(--oracle-digests "${concurrency_oracle}"); fi
  "${harness_cmd[@]}" | tee "${run_dir}/harness-summary.txt"
  qualifier_cmd=(python3 "${concurrency_qualifier}" --result "${run_dir}/result.json"
    --out "${run_dir}/qualification.json" --active-slots "${parallel}" --expected-oracle-rows "${concurrency}")
  if [[ "${baseline_mode}" == 1 ]]; then
    qualifier_cmd+=(--pilot --pilot-require-batch-gates --oracle-out "${run_dir}/oracle-digests.json")
  elif [[ "${pilot_mode}" == 1 ]]; then
    qualifier_cmd+=(--pilot --pilot-require-batch-gates --pilot-from-batch --oracle-out "${run_dir}/oracle-digests.json")
  fi
  "${qualifier_cmd[@]}"
  python3 - "${run_dir}" "${arm}" "${baseline_mode}" "${pilot_mode}" "${batch_size}" "${queue_settle_ms}" "${tp_size}" "${concurrency}" "${context}" "${feature_profile}" "${q8_dedup_override}" "${launch_stagger_ms}" "${wdc_q4k_name_filter}" "${mtp_depth}" "${candidate_kind}" "${q4k_f16_cache_filter}" "${pin_slots}" <<'PY'
import json, pathlib, sys
root, arm = pathlib.Path(sys.argv[1]), sys.argv[2]
baseline_mode = sys.argv[3] == "1"
pilot_mode = sys.argv[4] == "1"
batch_size, queue_settle_ms = int(sys.argv[5]), int(sys.argv[6])
tp_size, concurrency, context = map(int, sys.argv[7:10])
feature_profile = sys.argv[10]
q8_dedup_override = None if sys.argv[11] == "" else int(sys.argv[11])
launch_stagger_ms = int(sys.argv[12])
wdc_q4k_name_filter = sys.argv[13] or None
mtp_depth = int(sys.argv[14])
candidate_kind = sys.argv[15]
q4k_f16_cache_filter = sys.argv[16] or None
pin_slots = sys.argv[17] == "1"
result = json.loads((root / "result.json").read_text())
quality = json.loads((root / "qualification.json").read_text())
oracle_exact_all = all(batch.get("oracle_exact_all") is True for batch in result["batches"])
quality_qualified = quality.get("batch_gates_passed") is True and (baseline_mode or pilot_mode or oracle_exact_all)
summary = {
    "profile": "concurrency",
    "arm": arm,
    "baseline_generation": baseline_mode,
    "pilot_generation": pilot_mode,
    "publishable_measurement": not baseline_mode and not pilot_mode and quality_qualified,
    "quality_qualified": quality_qualified,
    "pinned_oracle_exact_all": oracle_exact_all,
    "pinned_oracle_exact_count": result["batches"][0].get("oracle_exact_count"),
    "pinned_oracle_exact_total": result["batches"][0].get("oracle_exact_total"),
    "sequential_oracle_exact_all": oracle_exact_all,
    "sequential_oracle_exact_count": result["batches"][0].get("oracle_exact_count"),
    "sequential_oracle_exact_total": result["batches"][0].get("oracle_exact_total"),
    "aggregate_tok_s": result["batches"][0]["aggregate_tok_s_wall"],
    "cached_tokens_all_zero": quality.get("cached_tokens_all_zero"),
    "complete_token_id_identity_all": quality.get("complete_token_id_identity_all"),
    "cross_base_oracle_collision_count": quality.get("cross_base_oracle_collision_count"),
    "batch_size": batch_size,
    "queue_settle_ms": queue_settle_ms,
    "tp_size": tp_size,
    "concurrency": concurrency,
    "context": context,
    "feature_profile": feature_profile,
    "q8_dedup_override": q8_dedup_override,
    "launch_stagger_ms": launch_stagger_ms,
    "wdc_q4k_name_filter": wdc_q4k_name_filter,
    "mtp_depth": mtp_depth,
    "candidate_kind": candidate_kind,
    "q4k_f16_cache_filter": q4k_f16_cache_filter,
    "pin_slots": pin_slots,
}
if concurrency == 64:
    summary["aggregate_tok_s_c64"] = result["batches"][0]["aggregate_tok_s_wall"]
(root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY
fi

curl -fsS "http://127.0.0.1:${port}/slots" >"${run_dir}/slots-after.json"
start=$(cat "${run_dir}/start-utc.txt")
journalctl -k -b --since "${start}" --no-pager | \
  grep -Ei 'llama-server.*segfault|xe.*(fault|reset|hang)|device lost|CAT fault|oom|out of memory' \
  >"${run_dir}/kernel-errors.txt" || true
[[ ! -s "${run_dir}/kernel-errors.txt" ]] || fail 'kernel error evidence found'
engaged=0; grep -q 'weight-decompression GEMM ENGAGED' "${run_dir}/server.log" && engaged=1
cache_engaged=0; grep -q 'Q4K-F16-CACHE: incumbent dequant bytes cached' "${run_dir}/server.log" && cache_engaged=1
if [[ "${profile}" == concurrency && "${arm}" == candidate && "${candidate_kind}" == wdc && "${engaged}" != 1 ]]; then fail 'candidate WDC liveness failed'; fi
if [[ "${arm}" == control && "${engaged}" != 0 ]]; then fail 'control WDC negative control failed'; fi
if [[ "${profile}" == concurrency && "${arm}" == candidate && "${candidate_kind}" == q4k-f16-cache && "${cache_engaged}" != 1 ]]; then fail 'candidate Q4_K F16 cache liveness failed'; fi
if [[ "${arm}" == control && "${cache_engaged}" != 0 ]]; then fail 'control Q4_K F16 cache negative control failed'; fi
printf '%s\n' "${engaged}" >"${run_dir}/wdc-engaged.txt"
printf '%s\n' "${cache_engaged}" >"${run_dir}/q4k-f16-cache-engaged.txt"
sha256sum "${run_dir}/result.json" "${run_dir}/summary.json" >"${run_dir}/result-sha256sums.txt"
if ! jq -e '.quality_qualified == true' "${run_dir}/summary.json" >/dev/null; then
  fail 'strict output-quality gate failed'
fi
printf 'PASS: %s\n' "${run_dir}"
