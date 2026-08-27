#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
target_dir=${TARGET_DIR:?set TARGET_DIR}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR}
build_dir=${BUILD_DIR:?set BUILD_DIR}
out_dir=${OUT_DIR:?set OUT_DIR to a new evidence directory}
arm=${ARM:?set ARM to mtp0 or mtp2}
attempt=${ATTEMPT:?set ATTEMPT}
oracle=${ORACLE_PATH:-}
port=${PORT:-18140}
campaign=qwen38-q4km-q4mtp-tp1-mixed-content-depth-20260827-r1
prereg=${repo}/experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1-prereg.json
fixture=${repo}/data/qwen27-exact-depth/qwen38-bce40ca-mixed-content-depth-v1.json
server=${build_dir}/bin/llama-server
backend=${build_dir}/bin/libggml-sycl.so
target=${target_dir}/Qwen3.8-27B-Q4_K_M.gguf
draft=${draft_dir}/mtp-Qwen3.8-27B-Q4_0.gguf

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ "${arm}" == mtp0 || "${arm}" == mtp2 ]] || fail 'ARM must be mtp0 or mtp2'
[[ ! -e "${out_dir}" ]] || fail "refusing to overwrite ${out_dir}"
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail 'PORT must be positive'
[[ -f "${prereg}" && -f "${fixture}" && -x "${server}" && -f "${backend}" ]] || fail 'sealed dependency missing'
[[ "$(sha256sum "${fixture}" | awk '{print $1}')" == a8a48b3549062759cc94b28f2360bea119f8adde582ace04928111b624d952ed ]] || fail 'fixture SHA mismatch'
[[ "$(sha256sum "${server}" | awk '{print $1}')" == 35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545 ]] || fail 'server SHA mismatch'
[[ "$(sha256sum "${backend}" | awk '{print $1}')" == 0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154 ]] || fail 'backend SHA mismatch'
if [[ "${arm}" == mtp2 ]]; then
  [[ -f "${oracle}" ]] || fail 'MTP2 requires ORACLE_PATH to the committed MTP0 summary'
fi

git -C "${repo}" fetch origin main --quiet
[[ "$(git -C "${repo}" rev-parse HEAD)" == "$(git -C "${repo}" rev-parse origin/main)" ]] || fail 'HEAD must equal origin/main'
[[ -z "$(git -C "${repo}" status --porcelain)" ]] || fail 'campaign requires a clean worktree'
exec 7>/run/lock/muse-glimmer-gpu-exclusive.lock
flock -n 7 || fail 'host-wide GPU campaign lock is held'
exec 8>/tmp/b70-benchmark.lock
flock -n 8 || fail 'host-wide benchmark lock is held'
exec 9>/tmp/b70-gpu0.lock
flock -n 9 || fail 'GPU0 lock is held'
pgrep -af 'llama-(server|bench|batched-bench)|vllm' >/dev/null && fail 'another model process is running'

mkdir -p "${out_dir}"
sha_inputs=("${prereg}" "${fixture}" "${server}" "${backend}")
if [[ "${arm}" == mtp2 ]]; then sha_inputs+=("${oracle}"); fi
sha256sum "${sha_inputs[@]}" >"${out_dir}/sha256sums.txt"
python3 "${repo}/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
  "${repo}/repro/qwen38-27b-q4km-tp1-b70/model-direct.json" "${target_dir}" \
  >"${out_dir}/target-model-verification.stdout"
if [[ "${arm}" == mtp2 ]]; then
  python3 "${repo}/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
    "${repo}/repro/qwen38-27b-q4km-mtp2-tp1-b70/draft-model-direct.json" "${draft_dir}" \
    >"${out_dir}/draft-model-verification.stdout"
fi
free -b >"${out_dir}/memory-before.txt"
xpu-smi dump -d 0 -m 0,1,2,3,4,5 -n 1 >"${out_dir}/xpu-before.txt" 2>&1 || true

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export GGML_SYCL_ENABLE_GRAPH=0 UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1
export GGML_SYCL_COMM_SINGLE_KERNEL=1 GGML_META_FUSE_ALLREDUCE_ADD=1 GGML_META_FUSE_ALLREDUCE_ADD_RMS_MUL=1
export GGML_SYCL_COMM_FUSED_Q8=1 GGML_SYCL_FUSED_SWIGLU_Q8=1 GGML_SYCL_FUSED_ATTN_Q8=1 GGML_SYCL_FUSED_GDN_Q8=1
export GGML_SYCL_FUSED_MMVQ_PAIR=1 GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K=1 GGML_SYCL_FUSED_MMVQ_PAIR_GDN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_ATTN=1 GGML_SYCL_FUSED_MMVQ_TRIPLE_GDN=1 GGML_SYCL_FUSED_MMVQ_QUAD_GDN=1
export GGML_SYCL_FUSED_GDN_BETA_SIGMOID=1 GGML_SYCL_FUSED_CONCAT_STATE=1 GGML_SYCL_FUSED_GDN_STATE_IO=1 GGML_SYCL_FUSED_CONV_STATE_IO=1
export GGML_SYCL_COMM_DIRECT_Q8=2 GGML_SYCL_FUSED_ROPE_SET_ROWS=1 GGML_SYCL_COMM_REDUCE_VEC4=1 GGML_SYCL_FUSED_QK_NORM_ROPE=1
export GGML_SYCL_FUSED_CONV_SILU_L2=1 GGML_SYCL_FUSE_EXT=31 GGML_SYCL_QDEDUP_STATS=1 GGML_SYCL_MMQ_Q4K_REORDER=1
unset GGML_SYCL_WDC GGML_SYCL_WDC_Q4K GGML_SYCL_REORDER_IN_GEMM GGML_SYCL_FORCE_REORDER GGML_SYCL_FORCE_REORDER_Q4K GGML_SYCL_DISABLE_REORDER_Q6K

common=(
  "${server}" --model "${target}" --device SYCL0 --gpu-layers 99 --split-mode none --fit off
  --cache-type-k f16 --cache-type-v f16 --flash-attn on --batch-size 2048 --ubatch-size 512
  --cache-ram 0 --ctx-checkpoints 0 --reasoning off --threads 16 --poll 50 --ctx-size 33024
  --parallel 1 --cont-batching --no-cache-prompt --slot-prompt-similarity 0 --metrics
  --host 127.0.0.1 --port "${port}"
)
if [[ "${arm}" == mtp2 ]]; then
  common+=(
    --model-draft "${draft}" --device-draft SYCL0 --gpu-layers-draft 99
    --spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-n-min 0 --spec-draft-p-min 0
    --cache-type-k-draft f16 --cache-type-v-draft f16
  )
fi

server_pid=
cleanup() {
  if pgrep -x llama-server >/dev/null; then pkill -TERM -x llama-server 2>/dev/null || true; fi
  if [[ -n "${server_pid:-}" ]]; then wait "${server_pid}" 2>/dev/null || true; fi
  free -b >"${out_dir}/memory-after.txt" 2>/dev/null || true
  xpu-smi dump -d 0 -m 0,1,2,3,4,5 -n 1 >"${out_dir}/xpu-after.txt" 2>&1 || true
}
trap cleanup EXIT INT TERM

systemd-run --user --scope --quiet --property=MemoryHigh=11G --property=MemoryMax=13G --property=MemorySwapMax=12G \
  "${common[@]}" >"${out_dir}/server.log" 2>&1 &
server_pid=$!
for _ in $(seq 1 600); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/health.json" 2>"${out_dir}/health.err"; then break; fi
  kill -0 "${server_pid}" 2>/dev/null || fail 'server exited before readiness'
  sleep 2
done
curl -fsS "http://127.0.0.1:${port}/health" >/dev/null || fail 'server readiness timeout'
curl -fsS "http://127.0.0.1:${port}/props" >"${out_dir}/props.json"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-before.txt" || true
python3 "${repo}/scripts/neural-download-canaries.py" \
  --base-url "http://127.0.0.1:${port}" --model "${campaign}-${arm}" \
  --out "${out_dir}/canaries-before.json" >"${out_dir}/canaries-before.stdout"

classes=(technical-prose python-code structured-docs)
depths=(2048 4096 8192 16384 24576 32768)
for depth in "${depths[@]}"; do
  for class in "${classes[@]}"; do
    case_id=${class}-depth-${depth}
    python3 "${repo}/scripts/bench-openai-token-depth-suite.py" \
      --execute --fixture "${fixture}" --depth "${depth}" --case-id "${case_id}" \
      --context-capacity 33024 --base-url "http://127.0.0.1:${port}" \
      --model "${campaign}-${arm}" --response-adapter llama-server --timeout 1800 \
      --out "${out_dir}/${case_id}.json" >"${out_dir}/${case_id}.stdout.json"
  done
done

python3 "${repo}/scripts/neural-download-canaries.py" \
  --base-url "http://127.0.0.1:${port}" --model "${campaign}-${arm}" \
  --out "${out_dir}/canaries-after.json" >"${out_dir}/canaries-after.stdout"
curl -fsS "http://127.0.0.1:${port}/metrics" >"${out_dir}/metrics-after.txt" || true

python3 - "${out_dir}" "${arm}" "${attempt}" "${campaign}" "${oracle}" >"${out_dir}/summary.json" <<'PY'
import json, math, pathlib, statistics, sys
root, arm, attempt, campaign, oracle_path = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
oracle = json.loads(pathlib.Path(oracle_path).read_text()) if oracle_path else None
expected = {row["case_id"]: row for row in oracle["cases"]} if oracle else {}
cases = []
for path in sorted(
    path for path in root.glob("*-depth-*.json")
    if not path.name.endswith(".stdout.json")
):
    row = json.loads(path.read_text())
    case_id = row["run_identity"]["case_id"]
    cls, depth_text = case_id.rsplit("-depth-", 1)
    output_hash = row["response"]["output_token_ids_sha256"]
    cases.append({
        "case_id": case_id,
        "class": cls,
        "active_context_tokens": int(depth_text),
        "receipt": path.name,
        "receipt_status": row["status"],
        "cache_zero": row["gate"]["checks"]["cached_tokens_zero"],
        "decode_tok_s": row["metric_window"]["conventional_99_interval_tok_s"],
        "ttft_ms": row["metric_window"]["time_to_first_token_s"] * 1000,
        "output_token_ids_sha256": output_hash,
        "output_token_ids": row["response"]["token_ids"],
        "target_oracle_exact": None if oracle is None else output_hash == expected[case_id]["output_token_ids_sha256"],
    })
before = json.loads((root / "canaries-before.json").read_text())
after = json.loads((root / "canaries-after.json").read_text())
metrics = (root / "metrics-after.txt").read_text(errors="replace")
def metric(name):
    for line in metrics.splitlines():
        if line.startswith(name + " "):
            return float(line.split()[-1])
    return None
drafted = metric("llamacpp:spec_decode_num_draft_tokens_total")
accepted = metric("llamacpp:spec_decode_num_accepted_tokens_total")
points = []
for depth in (2048, 4096, 8192, 16384, 24576, 32768):
    selected = [row for row in cases if row["active_context_tokens"] == depth]
    points.append({
        "active_context_tokens": depth,
        "classes": [row["class"] for row in selected],
        "samples": len(selected),
        "median_decode_tok_s": statistics.median(row["decode_tok_s"] for row in selected),
        "median_ttft_ms": statistics.median(row["ttft_ms"] for row in selected),
        "all_request_gates_passed": len(selected) == 3 and all(row["receipt_status"] == "passed" for row in selected),
        "all_target_oracle_exact": None if oracle is None else len(selected) == 3 and all(row["target_oracle_exact"] for row in selected),
    })
base_pass = len(cases) == 18 and all(row["receipt_status"] == "passed" and math.isfinite(row["decode_tok_s"]) for row in cases) and before["pass_all"] and after["pass_all"]
spec_pass = arm == "mtp0" or (drafted is not None and accepted is not None and drafted > 0 and accepted > 0 and all(row["target_oracle_exact"] for row in cases))
passed = base_pass and spec_pass
result = {
    "schema": "neural.download.qwen38-q4km-q4mtp-tp1-mixed-content-depth-arm.v1",
    "campaign_id": campaign,
    "arm": arm,
    "attempt": attempt,
    "status": "passed" if passed else "failed-closed",
    "classification": "Grade B three-class unrepeated real-content exact-depth HTTP evidence" if passed else "invalid-or-partial",
    "cases": cases,
    "points": points,
    "canaries": {"before": before["pass_all"], "after": after["pass_all"]},
    "draft_counters": {"drafted": drafted, "accepted": accepted, "acceptance_rate": accepted / drafted if drafted else None},
    "oracle": None if oracle is None else {"path": oracle_path, "campaign_id": oracle["campaign_id"], "attempt": oracle["attempt"]},
    "publication_boundary": "Per-depth medians across technical prose, Python code, and structured documentation only. Raw document continuation, not a natural retrieval/task suite. No interpolation, extrapolation, headline replacement, or LocalMaxxing authority."
}
json.dump(result, sys.stdout, indent=2, sort_keys=True); print()
if not passed: raise SystemExit(3)
PY

curl -fsS "http://127.0.0.1:${port}/health" >"${out_dir}/post-health.json"
trap - EXIT INT TERM
cleanup
printf 'PASS: %s\n' "${out_dir}"
