#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
depth=${MTP_DEPTH:?set MTP_DEPTH to 1 or 2}
attempt=${ATTEMPT:?set ATTEMPT to a unique attempt label}
target_dir=${TARGET_DIR:?set TARGET_DIR to the Qwen3.8 ggml-org GGUF directory}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR to the directory containing the pinned Unsloth MTP draft}
build_dir=${BUILD_DIR:?set BUILD_DIR to the accepted TP1 build directory}
out_dir=${OUT_DIR:?set OUT_DIR to a new evidence directory}
port=${PORT:-18141}
suite=${SUITE:-${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}
prereg=${repo}/experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-q4mtp-tp1-depth-screen-r1-prereg.json
oracle=${repo}/experiments/qwen38-27b-b70/data/qwen38-q8-tp1-strict-reasoningoff-native-20260827-r1b/performance.json
target=${target_dir}/Qwen3.8-27B-Q8_0.gguf
draft=${draft_dir}/mtp-Qwen3.8-27B-Q4_0.gguf
server=${build_dir}/bin/llama-server
backend=${build_dir}/bin/libggml-sycl.so
expected_server=35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545
expected_backend=0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154
expected_oracle=b1053f19962ba5c4f6a82c92939645f41ad8542f110a0df0ff4e7cbdbfbf82a9

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "${depth}" =~ ^(1|2)$ ]] || fail 'MTP_DEPTH must be 1 or 2'
[[ ! -e "${out_dir}" ]] || fail "refusing to overwrite ${out_dir}"
[[ -f "${target}" && -f "${draft}" && -x "${server}" && -f "${backend}" ]] || fail 'model/runtime artifact missing'
[[ "$(sha256sum "${server}" | awk '{print $1}')" == "${expected_server}" ]] || fail 'llama-server SHA-256 mismatch'
[[ "$(sha256sum "${backend}" | awk '{print $1}')" == "${expected_backend}" ]] || fail 'SYCL backend SHA-256 mismatch'
[[ "$(sha256sum "${oracle}" | awk '{print $1}')" == "${expected_oracle}" ]] || fail 'MTP0 oracle SHA-256 mismatch'
[[ -z "$(git -C "${repo}" status --porcelain)" ]] || fail 'repository must be clean'
[[ "$(git -C "${repo}" branch --show-current)" == main ]] || fail 'campaign must run from main'
[[ "$(git -C "${repo}" rev-parse HEAD)" == "$(git -C "${repo}" rev-parse origin/main)" ]] || fail 'main must be pushed before execution'

exec 7>/run/lock/muse-glimmer-gpu-exclusive.lock
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>/tmp/b70-gpu0.lock
flock -n 9 || fail 'GPU0 lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'

mkdir -p "${out_dir}"
"${repo}/repro/qwen38-27b-q8-tp1-b70/verify-model-direct.sh" "${target_dir}" \
  --json "${out_dir}/target-verification.json" >"${out_dir}/target-verification.stdout"
python3 "${repo}/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
  "${repo}/experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4mtp-draft-direct.json" "${draft_dir}" \
  --json "${out_dir}/draft-verification.json" >"${out_dir}/draft-verification.stdout"

python3 - "${out_dir}/campaign-identity.json" "${attempt}" "${depth}" "${target}" "${draft}" "${server}" "${backend}" "${suite}" "${prereg}" "${oracle}" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import sys

out, attempt, depth, target, draft, server, backend, suite, prereg, oracle = sys.argv[1:]
def digest(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
value = {
    "schema": "neural.download.qwen38-q8-q4mtp-tp1-screen-attempt.v1",
    "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "attempt": attempt,
    "profile": f"q8-target-q4mtp-tp1-depth{depth}-reasoning-off",
    "artifacts": {
        "target": {"path": target, "sha256": "f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8"},
        "draft": {"path": draft, "sha256": "50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e"},
        "server": {"path": server, "sha256": "35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545"},
        "backend": {"path": backend, "sha256": "0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154"},
        "suite": {"path": suite, "sha256": digest(suite)},
        "prereg": {"path": prereg, "sha256": digest(prereg)},
        "mtp0_oracle": {"path": oracle, "sha256": digest(oracle)},
    },
    "contract": {"mtp_depth": int(depth), "tp": 1, "gpu": 0, "target_kv": "f16", "draft_kv": "f16", "graph": "off", "reasoning": "off", "parallel_slots": 1, "configured_context_tokens": 1024, "prompt_cache": False, "prompt_count": 12, "prompt_classes": 6, "max_tokens": 512, "metric_events": 100, "metric_intervals": 99},
}
pathlib.Path(out).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY

server_pid=
cleanup() {
  if pgrep -x llama-server >/dev/null; then pkill -TERM -x llama-server 2>/dev/null || true; fi
  if [[ -n "${server_pid:-}" ]]; then wait "${server_pid}" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export GGML_SYCL_ENABLE_GRAPH=0
export UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
export UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1
export GGML_SYCL_COMM_SINGLE_KERNEL=1
export GGML_META_FUSE_ALLREDUCE_ADD=1
export GGML_META_FUSE_ALLREDUCE_ADD_RMS_MUL=1
export GGML_SYCL_COMM_FUSED_Q8=1
export GGML_SYCL_FUSED_SWIGLU_Q8=1
export GGML_SYCL_FUSED_ATTN_Q8=1
export GGML_SYCL_FUSED_GDN_Q8=1
export GGML_SYCL_FUSED_MMVQ_PAIR=1
export GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K=1
export GGML_SYCL_FUSED_MMVQ_PAIR_GDN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_ATTN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_GDN=1
export GGML_SYCL_FUSED_MMVQ_QUAD_GDN=1
export GGML_SYCL_FUSED_GDN_BETA_SIGMOID=1
export GGML_SYCL_FUSED_CONCAT_STATE=1
export GGML_SYCL_FUSED_GDN_STATE_IO=1
export GGML_SYCL_FUSED_CONV_STATE_IO=1
export GGML_SYCL_COMM_DIRECT_Q8=2
export GGML_SYCL_FUSED_ROPE_SET_ROWS=1
export GGML_SYCL_COMM_REDUCE_VEC4=1
export GGML_SYCL_FUSED_QK_NORM_ROPE=1
export GGML_SYCL_FUSED_CONV_SILU_L2=1
export GGML_SYCL_FUSE_EXT=31
export GGML_SYCL_QDEDUP_STATS=1
export GGML_SYCL_MMQ_Q4K_REORDER=1
unset GGML_SYCL_WDC GGML_SYCL_WDC_Q4K GGML_SYCL_REORDER_IN_GEMM
unset GGML_SYCL_FORCE_REORDER GGML_SYCL_FORCE_REORDER_Q4K GGML_SYCL_DISABLE_REORDER_Q6K

server_args=("${server}" --model "${target}" --device SYCL0 --gpu-layers 99 --split-mode none --fit off
  --model-draft "${draft}" --device-draft SYCL0 --gpu-layers-draft 99 --spec-type draft-mtp
  --spec-draft-n-max "${depth}" --spec-draft-n-min 0 --spec-draft-p-min 0
  --cache-type-k f16 --cache-type-v f16 --cache-type-k-draft f16 --cache-type-v-draft f16
  --flash-attn on --batch-size 2048 --ubatch-size 512 --cache-ram 0 --ctx-checkpoints 0
  --reasoning off --threads 16 --poll 50 --ctx-size 1024 --parallel 1 --cont-batching
  --no-cache-prompt --slot-prompt-similarity 0 --metrics --host 127.0.0.1 --port "${port}")
systemd-run --user --scope --quiet --property=MemoryHigh=11G --property=MemoryMax=13G --property=MemorySwapMax=12G \
  "${server_args[@]}" >"${out_dir}/server.log" 2>&1 &
server_pid=$!

for _ in $(seq 1 600); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/health.json" 2>"${out_dir}/health.err"; then break; fi
  kill -0 "${server_pid}" 2>/dev/null || fail 'server exited before readiness'
  sleep 2
done
curl -fsS "http://127.0.0.1:${port}/health" >/dev/null || fail 'server readiness timeout'
curl -fsS "http://127.0.0.1:${port}/props" >"${out_dir}/props.json" || true
curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-before.txt" || true
llama_pid=$(pgrep -n -x llama-server)
tr '\0' ' ' <"/proc/${llama_pid}/cmdline" >"${out_dir}/server-command.txt"; printf '\n' >>"${out_dir}/server-command.txt"
tr '\0' '\n' <"/proc/${llama_pid}/environ" | grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR=|SYCL_UR_USE_LEVEL_ZERO_V2=|ONEAPI_ROOT=|LD_LIBRARY_PATH=)' | LC_ALL=C sort >"${out_dir}/runtime-environment.txt"

python3 "${repo}/scripts/bench-openai-realistic-suite.py" \
  --base-url "http://127.0.0.1:${port}" --model "qwen38-q8-q4mtp-tp1-mtp${depth}" \
  --api-mode native-raw --suite "${suite}" --max-tokens 512 --metric-tokens 100 \
  --seed 42 --timeout 900 --return-token-ids --require-natural-eos \
  --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0,"top_p":1}' \
  --out "${out_dir}/performance.json" >"${out_dir}/performance.stdout"
python3 "${repo}/scripts/neural-download-canaries.py" \
  --base-url "http://127.0.0.1:${port}" --model "qwen38-q8-q4mtp-tp1-mtp${depth}" \
  --out "${out_dir}/canaries.json" >"${out_dir}/canaries.stdout"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-after.txt" || true

python3 - "${out_dir}/performance.json" "${out_dir}/canaries.json" "${oracle}" "${out_dir}/metrics-before.txt" "${out_dir}/metrics-after.txt" "${out_dir}/qualification.json" <<'PY'
import json
import pathlib
import re
import sys

performance_path, canary_path, oracle_path, before_path, after_path, out_path = sys.argv[1:]
p = json.load(open(performance_path)); c = json.load(open(canary_path)); o = json.load(open(oracle_path))
gate = p["realistic_final_gate"]; fresh = p["fresh_response_validity"]
metric = p["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
current = {row["prompt_id"]: row["token_ids"] for row in p["rows"]}
oracle = {row["prompt_id"]: row["token_ids"] for row in o["rows"]}
exact = sorted(key for key in oracle if current.get(key) == oracle[key])
def counters(path):
    text = pathlib.Path(path).read_text()
    values = {}
    for key in ("llamacpp:spec_decode_num_draft_tokens_total", "llamacpp:spec_decode_num_accepted_tokens_total"):
        matches = re.findall(rf"^{re.escape(key)}(?:\{{[^}}]*\}})?\s+([0-9.eE+-]+)$", text, re.M)
        values[key] = float(matches[-1]) if matches else 0.0
    return values
b = counters(before_path); a = counters(after_path)
drafted = a["llamacpp:spec_decode_num_draft_tokens_total"] - b["llamacpp:spec_decode_num_draft_tokens_total"]
accepted = a["llamacpp:spec_decode_num_accepted_tokens_total"] - b["llamacpp:spec_decode_num_accepted_tokens_total"]
passed = gate["passed"] and fresh["valid"] and gate["cached_tokens_all_zero"] and len(p["rows"]) == 12 and c["pass_all"] and len(exact) == 12 and drafted > 0 and accepted > 0
value = {
    "schema": "neural.download.qwen38-q8-q4mtp-tp1-screen-qualification.v1",
    "status": "passed" if passed else "failed-closed",
    "class_balanced_median_tok_s": metric,
    "target_oracle_exact_prompts": len(exact),
    "target_oracle_total_prompts": 12,
    "exact_prompt_ids": exact,
    "cached_tokens_all_zero": gate["cached_tokens_all_zero"],
    "objective_canaries_passed": c["pass_all"],
    "drafted_tokens": drafted,
    "accepted_tokens": accepted,
    "acceptance_rate": accepted / drafted if drafted else None,
    "publication_authority": "single-server screen only; no headline, 32K, concurrency, or cross-profile authority",
}
pathlib.Path(out_path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
if not passed: raise SystemExit("qualification failed closed")
print(f"class_balanced_median_tok_s={metric:.12f}")
print(f"target_oracle_exact_prompts={len(exact)}/12")
print(f"draft_acceptance_rate={accepted / drafted:.6f}")
PY

curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/post-health.json"
trap - EXIT INT TERM
cleanup
printf 'complete attempt=%s depth=%s evidence=%s\n' "${attempt}" "${depth}" "${out_dir}"
