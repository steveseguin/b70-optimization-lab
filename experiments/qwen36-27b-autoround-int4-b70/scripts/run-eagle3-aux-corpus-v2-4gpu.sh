#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v2-chat-4gpu-${STAMP}}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
SUITE="${SUITE:-experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v2-suite.json}"
OUTPUT_TOKENS="${OUTPUT_TOKENS:-160}"
SHARD_PROMPTS="${SHARD_PROMPTS:-24}"
BASE_PORT="${BASE_PORT:-19480}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
EAGLE3_AUX_LAYERS="${EAGLE3_AUX_LAYERS:-1,31,60}"

mkdir -p "$RUN_ROOT"

run_shard() {
  local shard="$1"
  local gpu="$2"
  local start_index="$3"
  local port=$((BASE_PORT + shard))
  local shard_dir="$RUN_ROOT/shard-$shard"
  mkdir -p "$shard_dir/dump" "$shard_dir/dataset" "$shard_dir/logs"
  (
    set -euo pipefail
    cd "$repo_dir"
    export MODEL_DIR
    export GPU_INDEX="$gpu"
    export PORT="$port"
    export HOST=127.0.0.1
    export MAX_MODEL_LEN=2048
    export MAX_NUM_BATCHED_TOKENS=1024
    export MAX_NUM_SEQS=1
    export GPU_MEMORY_UTILIZATION
    export QWEN36_27B_ENABLE_MTP=0
    export QWEN36_27B_ENABLE_XPU_GRAPH=1
    export QWEN36_27B_DEFAULT_ENABLE_THINKING=0
    export QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS=1
    export VLLM_XPU_LM_HEAD_INT8=1
    export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
    export VLLM_XPU_EAGLE_DATA_DUMP_DIR="$shard_dir/dump"
    export VLLM_XPU_EAGLE_DATA_DUMP_DTYPE=bfloat16
    export VLLM_XPU_EAGLE_DATA_DUMP_SINGLE_TOKEN_ONLY=1
    export VLLM_XPU_EAGLE_DATA_DUMP_AUX_LAYERS="$EAGLE3_AUX_LAYERS"
    export VLLM_XPU_EAGLE_DATA_DUMP_DEBUG_FILE="$shard_dir/logs/eagle-dump-debug.jsonl"
    export VLLM_XPU_EAGLE_DATA_DUMP_DEBUG_MAX_LINES=2000
    export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'

    experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh \
      > "$shard_dir/logs/server.stdout.log" 2>&1 &
    local server_pid=$!
    echo "$server_pid" > "$shard_dir/logs/server.pid"
    cleanup() {
      if kill -0 "$server_pid" 2>/dev/null; then
        kill "$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
      fi
    }
    trap cleanup EXIT

    local deadline=$((SECONDS + READINESS_TIMEOUT_S))
    until curl -fsS "http://127.0.0.1:${port}/v1/models" \
        > "$shard_dir/logs/models.json" \
        2> "$shard_dir/logs/models.err"; do
      if ! kill -0 "$server_pid" 2>/dev/null; then
        echo "server exited before readiness on shard $shard" >&2
        tail -80 "$shard_dir/logs/server.stdout.log" >&2 || true
        exit 1
      fi
      if (( SECONDS >= deadline )); then
        echo "timed out waiting for shard $shard readiness" >&2
        tail -80 "$shard_dir/logs/server.stdout.log" >&2 || true
        exit 1
      fi
      sleep 2
    done

    /home/steve/.venvs/vllm-xpu/bin/python scripts/collect-qwen36-eagle-hidden-corpus.py \
      --base-url "http://127.0.0.1:${port}" \
      --model qwen36-27b-int4-autoround \
      --tokenizer "$MODEL_DIR" \
      --suite "$SUITE" \
      --api-mode chat \
      --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
      --request-id-prefix "qwen27-eagle3-aux-v2-s${shard}" \
      --start-index "$start_index" \
      --num-prompts "$SHARD_PROMPTS" \
      --output-tokens "$OUTPUT_TOKENS" \
      --out "$shard_dir/collector-summary.json" \
      > "$shard_dir/logs/collector.stdout.log" 2>&1

    cleanup
    trap - EXIT

    /home/steve/.venvs/vllm-xpu/bin/python scripts/build-qwen36-eagle-dataset-from-dump.py \
      --dump-dir "$shard_dir/dump" \
      --out-dir "$shard_dir/dataset" \
      --metadata "$shard_dir/collector-summary.json" \
      --summary "$shard_dir/dataset-summary.json" \
      --allow-missing-current-token-ids \
      --reconstruct-positions-from-num-tokens \
      --min-len 8 \
      --max-len 2048 \
      --hidden-dtype bfloat16 \
      > "$shard_dir/logs/build-dataset.stdout.log" 2>&1
  ) > "$shard_dir/logs/shard.stdout.log" 2> "$shard_dir/logs/shard.stderr.log"
}

pids=()
for shard in 0 1 2 3; do
  run_shard "$shard" "$shard" "$((shard * SHARD_PROMPTS))" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

python3 - "$RUN_ROOT" "$EAGLE3_AUX_LAYERS" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
aux_layers = sys.argv[2]
shards = []
for shard_dir in sorted(root.glob("shard-*")):
    item = {"shard": shard_dir.name, "path": str(shard_dir)}
    for name in ("collector-summary.json", "dataset-summary.json"):
        path = shard_dir / name
        item[f"{name}_exists"] = path.exists()
        if path.exists():
            data = json.loads(path.read_text())
            if name.startswith("collector"):
                item["num_prompts"] = data.get("num_prompts")
                item["total_output_tokens_actual"] = data.get(
                    "total_output_tokens_actual")
                item["families"] = data.get("families")
            else:
                item["samples_saved"] = data.get("samples_saved")
                item["usable_rows"] = data.get("usable_rows")
                item["continuity_breaks"] = data.get("continuity_breaks")
                item["samples_with_metadata"] = data.get(
                    "samples_with_metadata")
                item["aux_rows_available"] = data.get("aux_rows_available")
                item["aux_rows_saved"] = data.get("aux_rows_saved")
                item["aux_bad_files"] = data.get("aux_bad_files")
    shards.append(item)

summary = {
    "classification": "diagnostic_only_eagle3_aux_corpus_v2_4gpu_collection",
    "run_root": str(root),
    "aux_layers": aux_layers,
    "shards": shards,
    "total_prompts": sum(s.get("num_prompts") or 0 for s in shards),
    "total_rows": sum(s.get("usable_rows") or 0 for s in shards),
    "total_samples": sum(s.get("samples_saved") or 0 for s in shards),
    "total_samples_with_metadata": sum(
        s.get("samples_with_metadata") or 0 for s in shards),
    "total_aux_rows_available": sum(
        s.get("aux_rows_available") or 0 for s in shards),
    "total_aux_rows_saved": sum(s.get("aux_rows_saved") or 0 for s in shards),
    "total_aux_bad_files": sum(s.get("aux_bad_files") or 0 for s in shards),
    "total_continuity_breaks": sum(s.get("continuity_breaks") or 0
                                    for s in shards),
}
(root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY

echo "$RUN_ROOT"
exit "$rc"
