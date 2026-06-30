#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
BASE_PORT="${BASE_PORT:-18520}"
MAX_TOKENS="${MAX_TOKENS:-96}"
CANARY_REPEATS="${CANARY_REPEATS:-8}"
LONG_CONTEXT_SUITE="${LONG_CONTEXT_SUITE:-$ROOT/repro/gemma4-26b-a4b-q8-b70/long-context-suite-v1.json}"
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="${LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS:-16384}"
LONG_CONTEXT_CASE_IDS="${LONG_CONTEXT_CASE_IDS:-}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"

# Format: GPU_INDEX:BATCH_SIZE:UBATCH_SIZE:TAG
LANE_SPECS="${LANE_SPECS:-0:1024:1024:ub1024-a 1:2048:2048:ub2048-a 2:1024:1024:ub1024-b 3:2048:2048:ub2048-b}"

echo "[gemma4-long-context-service] stamp=$STAMP"
echo "[gemma4-long-context-service] suite=$LONG_CONTEXT_SUITE"
echo "[gemma4-long-context-service] max_target_prompt_tokens=$LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS"
echo "[gemma4-long-context-service] case_ids=${LONG_CONTEXT_CASE_IDS:-<all selected by max>}"
echo "[gemma4-long-context-service] max_tokens=$MAX_TOKENS canary_repeats=$CANARY_REPEATS"
echo "[gemma4-long-context-service] lanes=$LANE_SPECS"

pids=()
labels=()

for spec in $LANE_SPECS; do
  IFS=: read -r gpu batch ubatch tag <<<"$spec"
  if [[ -z "$gpu" || -z "$batch" || -z "$ubatch" || -z "$tag" ]]; then
    echo "[gemma4-long-context-service] invalid lane spec: $spec" >&2
    exit 2
  fi

  port=$((BASE_PORT + gpu))
  label="gemma4-q8-gpu${gpu}-longctx-${tag}-ctx32768-o${MAX_TOKENS}-${STAMP}"
  driver_log="$ROOT/data/${label}.driver.log"
  labels+=("$label")

  echo "[gemma4-long-context-service] launching $label port=$port batch=$batch ubatch=$ubatch"
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
    REALISTIC_GATE=0 \
    LONG_CONTEXT_GATE=1 \
    LONG_CONTEXT_SUITE="$LONG_CONTEXT_SUITE" \
    LONG_CONTEXT_CASE_IDS="$LONG_CONTEXT_CASE_IDS" \
    LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="$LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS" \
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
    echo "[gemma4-long-context-service] PASS $label"
  else
    lane_rc=$?
    echo "[gemma4-long-context-service] FAIL rc=$lane_rc $label" >&2
    rc=1
  fi
done

summary="$ROOT/data/gemma4-long-context-service-gate-${STAMP}.json"
python3 - "$summary" "${labels[@]}" <<'PY'
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

out = Path(sys.argv[1])
labels = sys.argv[2:]
root = Path("/home/steve/qwen36-results-main")
rows = []

def stat(values):
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return None
    return {
        "count": len(vals),
        "mean": statistics.fmean(vals),
        "median": statistics.median(vals),
        "min": min(vals),
        "max": max(vals),
    }

for label in labels:
    run_dir = root / "data" / label
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        rows.append({"label": label, "status": "missing-summary", "run_dir": str(run_dir)})
        continue
    summary = json.loads(summary_path.read_text())
    launcher = summary.get("launcher_identity") or {}
    bench = summary.get("bench_summary") or {}
    long_gate = summary.get("long_context_gate") or {}
    long_path = run_dir / "long-context-suite.json"
    long = json.loads(long_path.read_text()) if long_path.exists() else {}
    long_rows = long.get("rows") or []
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
        "long_context_gate": long_gate,
        "quality_pass_all": bench.get("quality_pass_all"),
        "cached_tokens_all_zero": bench.get("cached_tokens_all_zero"),
        "prompts_unique": bench.get("prompts_unique"),
        "prefill_tok_s_approx": bench.get("prefill_tok_s_approx"),
        "ttft_s": bench.get("ttft_s"),
        "tok_s_after_ttft": bench.get("tok_s_after_ttft"),
        "tok_s_wall": bench.get("tok_s_wall"),
        "case_rows": [
            {
                "case_id": r.get("case_id"),
                "target_prompt_tokens": r.get("target_prompt_tokens"),
                "actual_prompt_tokens": r.get("prompt_tokens"),
                "ttft_s": r.get("ttft_s"),
                "prefill_tok_s_approx": r.get("prefill_tok_s_approx"),
                "tok_s_after_ttft": r.get("tok_s_after_ttft"),
                "cached_tokens": (((r.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens")),
                "validation_pass": ((r.get("validation") or {}).get("pass")),
                "prompt_sha256": r.get("prompt_sha256"),
                "output_sha256": r.get("sha256"),
            }
            for r in long_rows
        ],
    })

groups = defaultdict(list)
for row in rows:
    if row.get("status") == "ok":
        groups[(row.get("batch_size"), row.get("ubatch_size"))].append(row)

group_summaries = {}
for key, group_rows in groups.items():
    batch, ubatch = key
    med_prefills = []
    med_decode = []
    gate_passes = []
    for row in group_rows:
        prefill = row.get("prefill_tok_s_approx") or {}
        decode = row.get("tok_s_after_ttft") or {}
        med_prefills.append(prefill.get("median"))
        med_decode.append(decode.get("median"))
        gate_passes.append((row.get("long_context_gate") or {}).get("passed") is True)
    group_summaries[f"batch{batch}_ubatch{ubatch}"] = {
        "lanes": len(group_rows),
        "all_long_context_gates_passed": all(gate_passes) if gate_passes else False,
        "median_prefill_tok_s_by_lane": med_prefills,
        "median_prefill_tok_s_avg": statistics.fmean([v for v in med_prefills if isinstance(v, (int, float))]) if any(isinstance(v, (int, float)) for v in med_prefills) else None,
        "median_decode_tok_s_by_lane": med_decode,
        "median_decode_tok_s_avg": statistics.fmean([v for v in med_decode if isinstance(v, (int, float))]) if any(isinstance(v, (int, float)) for v in med_decode) else None,
    }

payload = {
    "kind": "gemma4_q8_long_context_service_gate",
    "policy": "service/prefill validation only; not a short-decode LocalMaxxing headline",
    "rows": rows,
    "group_summaries": group_summaries,
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(out)
PY

exit "$rc"
