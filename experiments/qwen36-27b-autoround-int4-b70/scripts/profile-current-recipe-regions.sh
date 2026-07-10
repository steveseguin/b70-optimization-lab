#!/usr/bin/env bash
set -euo pipefail

# Intrusive graph-none region timing for target-body attribution. This is a
# one-prompt diagnostic and must never be treated as headline throughput.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
GPU_INDEX="${GPU_INDEX:-1}"
PORT="${PORT:-19471}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
LABEL="${LABEL:-qwen27-current-recipe-graphnone-region-profile}"
PROFILE_FAMILY="${PROFILE_FAMILY:-coarse}"
BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-32}"
BENCH_METRIC_TOKENS="${BENCH_METRIC_TOKENS:-16}"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/profiles/$LABEL-$STAMP}"
OUT="$RUN_DIR/diagnostic-result.json"
SUITE="$RUN_DIR/one-prompt-suite.json"
TIMING_SUMMARY="$RUN_DIR/timing-summary.json"

if [[ ! -d "$MODEL_DIR" ]]; then
  echo "Model directory not found: $MODEL_DIR" >&2
  exit 2
fi
mkdir -p "$RUN_DIR"
"$PYTHON" - "$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" "$SUITE" <<'PY'
import json
import sys
from pathlib import Path

source = json.loads(Path(sys.argv[1]).read_text())
source["suite_id"] += "-diagnostic-first-prompt-only"
source["description"] = "Diagnostic first-prompt subset; not headline eligible."
source["prompts"] = source["prompts"][:1]
Path(sys.argv[2]).write_text(json.dumps(source, indent=2) + "\n")
PY

export VLLM_XPU_GDN_REPLAYSSM_SPEC=1
export VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8
export VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0
export VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=0
export VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1
export VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1
export VLLM_XPU_LM_HEAD_INT8=1
export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
export VLLM_XPU_DRAFT_LM_HEAD_INT4=1
export VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
export VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16
export VLLM_XPU_DECODE_TIMING=1
export VLLM_XPU_DECODE_TIMING_SYNC=1
export VLLM_XPU_DECODE_TIMING_SUMMARY=1
export VLLM_XPU_DECODE_TIMING_PRINT_EVERY=1
export VLLM_XPU_DECODE_TIMING_SKIP_FIRST=0
case "$PROFILE_FAMILY" in
  coarse)
    export VLLM_XPU_DECODE_TIMING_LABEL_REGEX='^(gpu_model_runner\.model_forward|qwen3_next\.(layer\.(linear_attention|full_attention|mlp)|final_norm))$'
    ;;
  gdn)
    export VLLM_XPU_DECODE_TIMING_LABEL_REGEX='^(gpu_model_runner\.model_forward|qwen3_next\.layer\.linear_attention|qwen3_next\.gdn\.(input_quant|qkvz_gemm_w8a8|ba_gemm_w8a8|qkvz_proj|ba_proj|core_op|replayssm_commit|replayssm_stage_alloc|replayssm_stage_conv|replayssm_recurrent_alloc|replayssm_recurrent|replayssm_pending_metadata|core_output_merge|output_norm|out_proj)|gdn_attention_core_xpu\.native)$'
    ;;
  *)
    echo "Unknown PROFILE_FAMILY: $PROFILE_FAMILY" >&2
    exit 2
    ;;
esac
export VLLM_XPU_DECODE_TIMING_SYNC_LABEL_REGEX="$VLLM_XPU_DECODE_TIMING_LABEL_REGEX"
cat > "$RUN_DIR/profile.env" <<EOF
classification=diagnostic_graphnone_region_timing_not_headline
model_dir=$MODEL_DIR
profile_family=$PROFILE_FAMILY
bench_max_tokens=$BENCH_MAX_TOKENS
bench_metric_tokens=$BENCH_METRIC_TOKENS
timing_label_regex=$VLLM_XPU_DECODE_TIMING_LABEL_REGEX
EOF

GPU_INDEX="$GPU_INDEX" \
PORT="$PORT" \
MODEL_DIR="$MODEL_DIR" \
LABEL="$LABEL" \
RUN_DIR="$RUN_DIR" \
OUT="$OUT" \
SUITE="$SUITE" \
BENCH_MAX_TOKENS="$BENCH_MAX_TOKENS" \
BENCH_METRIC_TOKENS="$BENCH_METRIC_TOKENS" \
QWEN36_27B_ENABLE_XPU_GRAPH=0 \
COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}' \
VLLM_EXTRA_ARGS='--enforce-eager' \
bash "$ROOT/scripts/run-qwen36-27b-autoround-vllm-candidate.sh"

"$PYTHON" "$ROOT/scripts/summarize-xpu-decode-timing-log.py" \
  --log "$RUN_DIR/server.stdout.log" \
  --out "$TIMING_SUMMARY" \
  --all-lines

"$PYTHON" - "$RUN_DIR/diagnostic-summary.json" "$OUT" "$TIMING_SUMMARY" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
result = json.loads(Path(sys.argv[2]).read_text())
timing = json.loads(Path(sys.argv[3]).read_text())
payload = {
    "classification": "diagnostic_graphnone_region_timing_not_headline",
    "valid_headline_throughput": False,
    "localmaxxing_eligible": False,
    "benchmark": result,
    "timing": timing,
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(out)
PY

echo "$RUN_DIR"
