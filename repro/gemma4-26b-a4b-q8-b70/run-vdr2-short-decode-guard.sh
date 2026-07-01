#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
BASE_PORT="${BASE_PORT:-18540}"
MAX_TOKENS="${MAX_TOKENS:-512}"
CANARY_REPEATS="${CANARY_REPEATS:-32}"
REALISTIC_METRIC_TOKENS="${REALISTIC_METRIC_TOKENS:-100}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"

# Format: GPU_INDEX:BATCH_SIZE:UBATCH_SIZE:TAG
LANE_SPECS="${LANE_SPECS:-0:1024:1024:ub1024-a 1:2048:2048:ub2048-a 2:1024:1024:ub1024-b 3:2048:2048:ub2048-b}"

echo "[gemma4-short-decode-guard] stamp=$STAMP"
echo "[gemma4-short-decode-guard] max_tokens=$MAX_TOKENS canary_repeats=$CANARY_REPEATS metric_tokens=$REALISTIC_METRIC_TOKENS"
echo "[gemma4-short-decode-guard] lanes=$LANE_SPECS"

pids=()
labels=()

for spec in $LANE_SPECS; do
  IFS=: read -r gpu batch ubatch tag <<<"$spec"
  if [[ -z "$gpu" || -z "$batch" || -z "$ubatch" || -z "$tag" ]]; then
    echo "[gemma4-short-decode-guard] invalid lane spec: $spec" >&2
    exit 2
  fi

  port=$((BASE_PORT + gpu))
  label="gemma4-q8-gpu${gpu}-shortguard-${tag}-ctx32768-o${MAX_TOKENS}-${STAMP}"
  driver_log="$ROOT/data/${label}.driver.log"
  labels+=("$label")

  echo "[gemma4-short-decode-guard] launching $label port=$port batch=$batch ubatch=$ubatch"
  (
    GPU_INDEX="$gpu" \
    PORT="$port" \
    LABEL="$label" \
    CTX_SIZE=32768 \
    FLASH_ATTN=on \
    GGML_SYCL_ENABLE_VMM=1 \
    BATCH_SIZE="$batch" \
    UBATCH_SIZE="$ubatch" \
    MAX_TOKENS="$MAX_TOKENS" \
    CANARY_REPEATS="$CANARY_REPEATS" \
    REALISTIC_GATE=1 \
    REALISTIC_METRIC_TOKENS="$REALISTIC_METRIC_TOKENS" \
    READINESS_TIMEOUT_S="$READINESS_TIMEOUT_S" \
    "$ROOT/repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh"
  ) >"$driver_log" 2>&1 &
  pids+=("$!")
done

rc=0
for i in "${!pids[@]}"; do
  pid="${pids[$i]}"
  label="${labels[$i]}"
  if wait "$pid"; then
    echo "[gemma4-short-decode-guard] PASS $label"
  else
    lane_rc=$?
    echo "[gemma4-short-decode-guard] FAIL rc=$lane_rc $label" >&2
    rc=1
  fi
done

summary="$ROOT/data/gemma4-short-decode-guard-${STAMP}.json"
python3 - "$summary" "${labels[@]}" <<'PY'
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

out = Path(sys.argv[1])
labels = sys.argv[2:]
root = out.parent.parent
rows = []

for label in labels:
    run_dir = root / "data" / label
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        rows.append({"label": label, "status": "missing-summary", "run_dir": str(run_dir)})
        continue
    summary = json.loads(summary_path.read_text())
    launcher = summary.get("launcher_identity") or {}
    bench = summary.get("bench_summary") or {}
    metric = bench.get("tok_s_1_100_after_ttft") or {}
    full = bench.get("tok_s_after_ttft_full") or {}
    wall = bench.get("tok_s_wall_full") or {}
    ttft = bench.get("ttft_ms") or {}
    gate = summary.get("realistic_final_gate") or {}
    rows.append({
        "label": label,
        "status": "ok",
        "run_dir": str(run_dir),
        "gpu_index": launcher.get("gpu_index"),
        "batch_size": launcher.get("batch_size"),
        "ubatch_size": launcher.get("ubatch_size"),
        "ctx_size": launcher.get("ctx_size"),
        "flash_attn": launcher.get("flash_attn"),
        "vmm": launcher.get("ggml_sycl_enable_vmm"),
        "canary_pass_all": summary.get("canary_pass_all"),
        "canary_rows_completed": summary.get("canary_rows_completed"),
        "realistic_gate_passed": gate.get("passed"),
        "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
        "tok_s_1_100_after_ttft_median": metric.get("median"),
        "tok_s_1_100_after_ttft_p10": metric.get("p10"),
        "tok_s_1_100_after_ttft_mean": metric.get("mean"),
        "tok_s_after_ttft_full_median": full.get("median"),
        "tok_s_wall_full_median": wall.get("median"),
        "ttft_ms_median": ttft.get("median"),
    })

groups = defaultdict(list)
for row in rows:
    if row.get("status") == "ok":
        groups[(row.get("batch_size"), row.get("ubatch_size"))].append(row)

group_summaries = {}
for key, group_rows in groups.items():
    batch, ubatch = key
    vals = [
        row.get("tok_s_1_100_after_ttft_median")
        for row in group_rows
        if isinstance(row.get("tok_s_1_100_after_ttft_median"), (int, float))
    ]
    group_summaries[f"batch{batch}_ubatch{ubatch}"] = {
        "lanes": len(group_rows),
        "all_realistic_gates_passed": all(row.get("realistic_gate_passed") is True for row in group_rows),
        "all_cached_tokens_zero": all(row.get("cached_tokens_all_zero") is True for row in group_rows),
        "median_tok_s_1_100_by_lane": vals,
        "median_tok_s_1_100_avg": statistics.fmean(vals) if vals else None,
    }

payload = {
    "kind": "gemma4_q8_short_decode_guard",
    "policy": "fixed realistic suite regression guard for service/prefill candidate; submit only if it beats the current record independently",
    "current_record_tok_s_1_100_after_ttft": 123.67689864739785,
    "rows": rows,
    "group_summaries": group_summaries,
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(out)
PY

exit "$rc"
