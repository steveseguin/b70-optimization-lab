#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle1-endpoint-isolation-${STAMP}}"
DRAFTER="${DRAFTER:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-4gpu-trainheldout-20260704T075504Z/draft-e6-r3-lr3e5-tok01}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
SUITE="${SUITE:-experiments/qwen36-27b-autoround-int4-b70/calibration-suite-v1.json}"
BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-128}"
BENCH_METRIC_TOKENS="${BENCH_METRIC_TOKENS:-100}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
VARIANT_TIMEOUT_S="${VARIANT_TIMEOUT_S:-3600}"

mkdir -p "$RUN_ROOT"

run_variant() {
  local label="$1"
  local gpu="$2"
  local port="$3"
  local promote="$4"
  local postprocess="$5"
  local graph="$6"
  local cg_config="$7"
  local spec_tokens="$8"

  local run_dir="$RUN_ROOT/$label"
  local out="$RUN_ROOT/$label.json"
  mkdir -p "$run_dir"
  (
    set -euo pipefail
    export LABEL="$label"
    export GPU_INDEX="$gpu"
    export PORT="$port"
    export RUN_DIR="$run_dir"
    export OUT="$out"
    export MODEL_DIR
    export SUITE
    export BENCH_MAX_TOKENS
    export BENCH_METRIC_TOKENS
    export READINESS_TIMEOUT_S
    export BENCH_REQUEST_EXTRA_JSON='{"chat_template_kwargs":{"enable_thinking":false}}'
    export QWEN36_27B_ENABLE_MTP=0
    export QWEN36_27B_ENABLE_XPU_GRAPH="$graph"
    export COMPILATION_CONFIG="$cg_config"
    export MAX_MODEL_LEN=2048
    export MAX_NUM_BATCHED_TOKENS=1024
    export MAX_NUM_SEQS=1
    export VLLM_XPU_LM_HEAD_INT8=1
    export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
    export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE="$promote"
    export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE="$postprocess"
    export VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE="$run_dir/verify-trace.jsonl"
    export VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_MAX_LINES="${VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_MAX_LINES:-20000}"
    export VLLM_EXTRA_ARGS
    VLLM_EXTRA_ARGS=$(printf \
      -- '--speculative-config {"method":"eagle","model":"%s","num_speculative_tokens":%s}' \
      "$DRAFTER" "$spec_tokens")
    timeout --kill-after=60s "$VARIANT_TIMEOUT_S" \
      bash scripts/run-qwen36-27b-autoround-vllm-candidate.sh
  ) > "$run_dir/runner.stdout.log" 2> "$run_dir/runner.stderr.log"
}

declare -a pids=()

run_variant \
  "eagle1-currentstate-graph-k3" \
  0 19440 1 0 1 \
  '{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
  3 &
pids+=("$!")

run_variant \
  "eagle1-defaultstate-graph-k3" \
  1 19441 0 1 1 \
  '{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
  3 &
pids+=("$!")

run_variant \
  "eagle1-currentstate-eager-k3" \
  2 19442 1 0 0 \
  '{"cudagraph_mode":"NONE","max_cudagraph_capture_size":0}' \
  3 &
pids+=("$!")

run_variant \
  "eagle1-currentstate-graph-k1" \
  3 19443 1 0 1 \
  '{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
  1 &
pids+=("$!")

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

python3 - "$RUN_ROOT" <<'PY'
import json
import re
import sys
from pathlib import Path

run_root = Path(sys.argv[1])
records = []
repeat_re = re.compile(r"\b(\w{3,}|[\u4e00-\u9fff])(?:\s+\1){4,}")
for path in sorted(run_root.glob("eagle1-*.json")):
    item = {
        "label": path.stem,
        "path": str(path),
        "exists": path.exists(),
    }
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        item["error"] = repr(exc)
        records.append(item)
        continue
    gate = data.get("realistic_final_gate", {})
    summary = data.get("summary", {})
    metric = summary.get("tok_s_1_100_after_ttft", {})
    ttft = summary.get("ttft_ms", {})
    rows = data.get("rows", [])
    repeats = []
    short_rows = []
    for row in rows:
        preview = row.get("text_preview") or ""
        if repeat_re.search(preview):
            repeats.append({
                "prompt_id": row.get("prompt_id"),
                "preview": preview[:220],
                "tok_s": row.get("tok_s_1_100_after_ttft"),
            })
        if row.get("stream_token_id_count", 0) < gate.get("metric_tokens", 100):
            short_rows.append({
                "prompt_id": row.get("prompt_id"),
                "stream_token_id_count": row.get("stream_token_id_count"),
                "preview": preview[:160],
            })
    item.update({
        "passed": gate.get("passed"),
        "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
        "metric_count": metric.get("count"),
        "median_tok_s_1_100_after_ttft": metric.get("median"),
        "p10_tok_s_1_100_after_ttft": metric.get("p10"),
        "mean_tok_s_1_100_after_ttft": metric.get("mean"),
        "median_ttft_ms": ttft.get("median"),
        "repeat_preview_count": len(repeats),
        "repeat_previews": repeats[:8],
        "short_metric_rows": short_rows[:8],
    })
    records.append(item)

summary = {
    "run_root": str(run_root),
    "classification": "diagnostic_only_endpoint_isolation",
    "policy": "Uses calibration-suite-v1 only; not a LocalMaxxing or headline record.",
    "records": records,
}
(run_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY

echo "$RUN_ROOT"
exit "$rc"
