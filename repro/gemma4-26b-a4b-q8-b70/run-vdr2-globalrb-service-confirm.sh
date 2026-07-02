#!/usr/bin/env bash
set -euo pipefail

# Reproduce the Gemma 4 26B Q8 long-context service A/B for the experimental
# host-derived global FlashAttention right-bound path.
#
# This is a service/prefill validation wrapper, not a short-decode
# LocalMaxxing record command. It compares:
#   control:   phase prefill 2048/1024 + GQA8 tile selector + SWA left-bound
#   candidate: control + LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND=1
#
# The A/B then swaps GPU assignment, so device variance does not masquerade as
# a source win.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)-globalrb-service-confirm}"
BASE_PORT="${BASE_PORT:-18640}"
LONG_CONTEXT_CASE_IDS="${LONG_CONTEXT_CASE_IDS:-lc-12288-early lc-16384-late lc-22000-middle}"
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="${LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS:-24000}"
CANARY_REPEATS_LONG="${CANARY_REPEATS_LONG:-2}"
MAX_TOKENS_LONG="${MAX_TOKENS_LONG:-96}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"

run_round() {
  local round="$1"
  local base_port="$2"
  shift 2
  local specs=("$@")
  local pids=()
  local labels=()
  local variants=()

  echo "[gemma4-globalrb-confirm] round=$round specs=${specs[*]}"
  for spec in "${specs[@]}"; do
    IFS=: read -r gpu variant on <<<"$spec"
    if [[ -z "$gpu" || -z "$variant" || -z "$on" ]]; then
      echo "[gemma4-globalrb-confirm] invalid spec: $spec" >&2
      exit 2
    fi

    local port=$((base_port + gpu))
    local label="gemma4-q8-gpu${gpu}-longctx-${variant}-globalrb-${STAMP}-${round}"
    labels+=("$label")
    variants+=("$variant")

    (
      export GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
      export LLAMA_PREFILL_UBATCH_SIZE=2048
      export LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1
      export LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048
      if [[ "$on" == "1" ]]; then
        export LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND=1
        export LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND_MIN_Q=2048
      else
        unset LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND
        unset LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND_MIN_Q
      fi

      GPU_INDEX="$gpu" \
      PORT="$port" \
      LABEL="$label" \
      CTX_SIZE=32768 \
      FLASH_ATTN=on \
      GGML_SYCL_ENABLE_VMM=1 \
      BATCH_SIZE=2048 \
      UBATCH_SIZE=1024 \
      MAX_TOKENS="$MAX_TOKENS_LONG" \
      CANARY_REPEATS="$CANARY_REPEATS_LONG" \
      REALISTIC_GATE=0 \
      LONG_CONTEXT_GATE=1 \
      LONG_CONTEXT_CASE_IDS="$LONG_CONTEXT_CASE_IDS" \
      LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="$LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS" \
      READINESS_TIMEOUT_S="$READINESS_TIMEOUT_S" \
      "$ROOT/repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh"
    ) >"$ROOT/data/${label}.driver.log" 2>&1 &
    pids+=("$!")
  done

  local rc=0
  for i in "${!pids[@]}"; do
    if wait "${pids[$i]}"; then
      echo "[gemma4-globalrb-confirm] PASS ${variants[$i]} ${labels[$i]}"
    else
      local lane_rc=$?
      echo "[gemma4-globalrb-confirm] FAIL rc=$lane_rc ${variants[$i]} ${labels[$i]}" >&2
      rc=1
    fi
  done

  local label_file="$ROOT/data/gemma4-globalrb-confirm-labels-${STAMP}-${round}.txt"
  : > "$label_file"
  for i in "${!labels[@]}"; do
    printf '%s %s\n' "${variants[$i]}" "${labels[$i]}" >> "$label_file"
  done
  echo "[gemma4-globalrb-confirm] labels=$label_file"
  return "$rc"
}

run_round long-ab "$BASE_PORT" \
  '0:control:0' '1:globalrb:1' '2:control:0' '3:globalrb:1'

run_round long-xover "$((BASE_PORT + 20))" \
  '0:globalrb:1' '1:control:0' '2:globalrb:1' '3:control:0'

python3 - "$ROOT" "$STAMP" <<'PY'
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
stamp = sys.argv[2]
data_dir = root / "data"


def mean(values):
    return statistics.fmean(values) if values else None


def median(values):
    return statistics.median(values) if values else None


def label_rows(label_file: Path, round_name: str):
    for line in label_file.read_text().splitlines():
        if not line.strip():
            continue
        variant, label = line.split(maxsplit=1)
        yield variant, label, round_name


rows = []
label_files = [
    (data_dir / f"gemma4-globalrb-confirm-labels-{stamp}-long-ab.txt",
     "long_ab"),
    (data_dir / f"gemma4-globalrb-confirm-labels-{stamp}-long-xover.txt",
     "long_xover"),
]

for label_file, round_name in label_files:
    if not label_file.exists():
        raise SystemExit(f"missing label file: {label_file}")
    for variant, label, round_label in label_rows(label_file, round_name):
        run_dir = data_dir / label
        summary_path = run_dir / "summary.json"
        suite_path = run_dir / "long-context-suite.json"
        if not summary_path.exists():
            raise SystemExit(f"missing summary: {summary_path}")
        if not suite_path.exists():
            raise SystemExit(f"missing long-context suite: {suite_path}")

        summary = json.loads(summary_path.read_text())
        suite = json.loads(suite_path.read_text())
        launcher = summary.get("launcher_identity", {})
        for case in suite.get("rows", []):
            rows.append({
                "variant": variant,
                "label": label,
                "round": round_label,
                "run_dir": str(run_dir),
                "gpu_index": launcher.get("gpu_index"),
                "case_id": case.get("case_id"),
                "prompt_tokens": case.get("prompt_tokens"),
                "prefill_tok_s_approx": case.get("prefill_tok_s_approx"),
                "tok_s_after_ttft": case.get("tok_s_after_ttft"),
                "ttft_s": case.get("ttft_s"),
                "cached_tokens": (
                    case.get("usage", {})
                    .get("prompt_tokens_details", {})
                    .get("cached_tokens")
                ),
                "validation_pass": (
                    case.get("validation", {}).get("pass")
                ),
                "canary_pass_all": summary.get("canary_pass_all"),
                "prompt_sha256": case.get("prompt_sha256"),
                "output_sha256": case.get("sha256"),
                "swa_left_bound": launcher.get(
                    "llama_experimental_swa_fattn_left_bound"),
                "swa_left_bound_min_q": launcher.get(
                    "llama_experimental_swa_fattn_left_bound_min_q"),
                "global_right_bound": launcher.get(
                    "llama_experimental_global_fattn_right_bound"),
                "global_right_bound_min_q": launcher.get(
                    "llama_experimental_global_fattn_right_bound_min_q"),
            })

by_variant = {}
for row in rows:
    by_variant.setdefault(row["variant"], []).append(row)

summary_by_variant = {}
for variant, variant_rows in sorted(by_variant.items()):
    prefill = [
        row["prefill_tok_s_approx"] for row in variant_rows
        if row.get("prefill_tok_s_approx") is not None
    ]
    decode = [
        row["tok_s_after_ttft"] for row in variant_rows
        if row.get("tok_s_after_ttft") is not None
    ]
    summary_by_variant[variant] = {
        "count": len(variant_rows),
        "prefill_min": min(prefill) if prefill else None,
        "prefill_max": max(prefill) if prefill else None,
        "prefill_mean": mean(prefill),
        "prefill_median": median(prefill),
        "decode_mean": mean(decode),
        "decode_median": median(decode),
    }

control_mean = summary_by_variant.get("control", {}).get("prefill_mean")
candidate_mean = summary_by_variant.get("globalrb", {}).get("prefill_mean")
ratio = None
delta_pct = None
decision = "inconclusive"
decision_reason = "missing control or candidate prefill data"
if control_mean and candidate_mean:
    ratio = candidate_mean / control_mean
    delta_pct = (ratio - 1.0) * 100.0
    if candidate_mean > control_mean:
        decision = "promote_candidate_for_followup"
        decision_reason = (
            "global-right-bound candidate improved mean prefill after "
            "GPU crossover while preserving correctness"
        )
    else:
        decision = "negative"
        decision_reason = (
            "global-right-bound candidate lost prefill after GPU crossover "
            "while preserving correctness"
        )

out = {
    "kind": "gemma4_global_fattn_right_bound_ab_crossover",
    "policy": (
        "service/prefill diagnostic only; not a LocalMaxxing short-decode "
        "headline"
    ),
    "rows": rows,
    "summary_by_variant": summary_by_variant,
    "control_prefill_mean": control_mean,
    "candidate_prefill_mean": candidate_mean,
    "candidate_over_control_mean_ratio": ratio,
    "candidate_delta_pct": delta_pct,
    "all_cached_tokens_zero": all(row.get("cached_tokens") == 0
                                  for row in rows),
    "all_validation_passed": all(row.get("validation_pass") is True
                                 for row in rows),
    "all_canary_passed": all(row.get("canary_pass_all") is True
                             for row in rows),
    "decision": decision,
    "decision_reason": decision_reason,
}

out_path = data_dir / f"gemma4-globalrb-comparison-{stamp}.json"
out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(f"[gemma4-globalrb-confirm] comparison={out_path}")
print(json.dumps({
    "decision": decision,
    "control_prefill_mean": control_mean,
    "candidate_prefill_mean": candidate_mean,
    "candidate_delta_pct": delta_pct,
    "all_cached_tokens_zero": out["all_cached_tokens_zero"],
    "all_validation_passed": out["all_validation_passed"],
    "all_canary_passed": out["all_canary_passed"],
}, indent=2, sort_keys=True))
PY
