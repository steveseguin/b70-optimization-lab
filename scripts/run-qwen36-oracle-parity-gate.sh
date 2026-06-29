#!/usr/bin/env bash
set -uo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <label>" >&2
  echo "requires ACCEPTED_TRACE_JSON and CANDIDATE_TRACE_JSON" >&2
  exit 2
fi

LABEL="$1"
ROOT="${ROOT:-/home/steve/llm-optimizations}"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
TOKENIZER="${TOKENIZER:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
STAMP="${STAMP:-$(date -u +%Y%m%d%H%M%S)}"

ACCEPTED_TRACE_JSON="${ACCEPTED_TRACE_JSON:-}"
CANDIDATE_TRACE_JSON="${CANDIDATE_TRACE_JSON:-}"
SPEC_TRACE_JSONL="${SPEC_TRACE_JSONL:-}"
SPEC_SUMMARY_JSON="${SPEC_SUMMARY_JSON:-}"
REPLAY_JSON="${REPLAY_JSON:-}"

FIXTURE_JSON="${FIXTURE_JSON:-$DATA_DIR/qwen36-oracle-$LABEL-fixture-$STAMP.json}"
FIXTURE_MD="${FIXTURE_MD:-$DATA_DIR/qwen36-oracle-$LABEL-fixture-$STAMP.md}"
REPLAY_OUT_JSON="${REPLAY_OUT_JSON:-$DATA_DIR/qwen36-oracle-$LABEL-spec-replay-$STAMP.json}"
REPLAY_OUT_MD="${REPLAY_OUT_MD:-$DATA_DIR/qwen36-oracle-$LABEL-spec-replay-$STAMP.md}"
SUMMARY_JSON="${SUMMARY_JSON:-$DATA_DIR/qwen36-oracle-$LABEL-gate-summary-$STAMP.json}"
SPEC_SUMMARY_JSON="${SPEC_SUMMARY_JSON:-$DATA_DIR/qwen36-oracle-$LABEL-spec-summary-$STAMP.json}"

MODE="${MODE:-exact}"
EXPECTED_MISMATCHES="${EXPECTED_MISMATCHES:-0}"
EXPECTED_ROLES="${EXPECTED_ROLES:-}"
EXPECT_SPEC_ACTIVE="${EXPECT_SPEC_ACTIVE:-1}"
REQUIRE_SPEC_JOIN="${REQUIRE_SPEC_JOIN:-1}"
MIN_DRAFT_TOKENS="${MIN_DRAFT_TOKENS:-1}"
MIN_ACCEPTED_TOKENS="${MIN_ACCEPTED_TOKENS:-1}"
MIN_ACCEPT_RATE_PCT="${MIN_ACCEPT_RATE_PCT:-}"
ALLOW_REPLAY_ACCOUNTING_MISMATCH="${ALLOW_REPLAY_ACCOUNTING_MISMATCH:-0}"

mkdir -p "$DATA_DIR"

if [[ -z "$ACCEPTED_TRACE_JSON" || -z "$CANDIDATE_TRACE_JSON" ]]; then
  echo "ACCEPTED_TRACE_JSON and CANDIDATE_TRACE_JSON are required" >&2
  exit 2
fi
if [[ ! -f "$ACCEPTED_TRACE_JSON" ]]; then
  echo "accepted trace not found: $ACCEPTED_TRACE_JSON" >&2
  exit 2
fi
if [[ ! -f "$CANDIDATE_TRACE_JSON" ]]; then
  echo "candidate trace not found: $CANDIDATE_TRACE_JSON" >&2
  exit 2
fi

replay_rc=0
if [[ -n "$SPEC_TRACE_JSONL" ]]; then
  if [[ "${REBUILD_SPEC_SUMMARY:-1}" == "1" || ! -f "$SPEC_SUMMARY_JSON" ]]; then
    echo "[oracle:$LABEL] summarizing spec trace"
    "$PYTHON" "$ROOT/scripts/summarize-qwen36-spec-trace.py" \
      --trace-jsonl "$SPEC_TRACE_JSONL" \
      --quality-json "candidate=$CANDIDATE_TRACE_JSON" \
      --out-json "$SPEC_SUMMARY_JSON"
  fi

  echo "[oracle:$LABEL] replaying spec trace"
  "$PYTHON" "$ROOT/scripts/replay-qwen36-spec-trace.py" \
    --trace-jsonl "$SPEC_TRACE_JSONL" \
    --tokenizer "$TOKENIZER" \
    --token-trace-json "$CANDIDATE_TRACE_JSON" \
    --out-json "$REPLAY_OUT_JSON" \
    --out-md "$REPLAY_OUT_MD"
  replay_rc=$?
  REPLAY_JSON="$REPLAY_OUT_JSON"
fi

reduce_args=(
  "$ROOT/scripts/reduce-qwen36-oracle-fixture.py"
  --accepted "$ACCEPTED_TRACE_JSON"
  --candidate "$CANDIDATE_TRACE_JSON"
  --tokenizer "$TOKENIZER"
  --output-json "$FIXTURE_JSON"
  --output-md "$FIXTURE_MD"
)
if [[ -n "$SPEC_SUMMARY_JSON" ]]; then
  reduce_args+=(--spec-summary "$SPEC_SUMMARY_JSON")
fi
if [[ -n "$REPLAY_JSON" ]]; then
  reduce_args+=(--replay-json "$REPLAY_JSON")
fi

echo "[oracle:$LABEL] reducing accepted/candidate fixture"
"$PYTHON" "${reduce_args[@]}"
reduce_rc=$?

check_args=(
  "$ROOT/scripts/check-qwen36-oracle-fixture.py"
  --fixture "$FIXTURE_JSON"
  --mode "$MODE"
)
if [[ -n "$REPLAY_JSON" ]]; then
  check_args+=(--replay-json "$REPLAY_JSON")
fi
if [[ -n "$SPEC_SUMMARY_JSON" ]]; then
  check_args+=(--spec-summary "$SPEC_SUMMARY_JSON")
fi
if [[ "$MODE" == "known-drift" ]]; then
  check_args+=(--expected-mismatches "$EXPECTED_MISMATCHES")
  if [[ -n "$EXPECTED_ROLES" ]]; then
    check_args+=(--expected-roles "$EXPECTED_ROLES")
  fi
fi
if [[ "$EXPECT_SPEC_ACTIVE" == "1" ]]; then
  check_args+=(--expect-spec-active)
fi
if [[ "$REQUIRE_SPEC_JOIN" == "1" ]]; then
  check_args+=(--require-spec-join)
fi
if [[ "$ALLOW_REPLAY_ACCOUNTING_MISMATCH" == "1" ]]; then
  check_args+=(--allow-replay-accounting-mismatch)
fi
if [[ "$MIN_DRAFT_TOKENS" != "0" ]]; then
  check_args+=(--min-draft-tokens "$MIN_DRAFT_TOKENS")
fi
if [[ "$MIN_ACCEPTED_TOKENS" != "0" ]]; then
  check_args+=(--min-accepted-tokens "$MIN_ACCEPTED_TOKENS")
fi
if [[ -n "$MIN_ACCEPT_RATE_PCT" ]]; then
  check_args+=(--min-accept-rate-pct "$MIN_ACCEPT_RATE_PCT")
fi

echo "[oracle:$LABEL] checking parity gate"
"$PYTHON" "${check_args[@]}"
check_rc=$?

"$PYTHON" - "$SUMMARY_JSON" <<PY
import json
from pathlib import Path

summary = {
    "label": "$LABEL",
    "stamp": "$STAMP",
    "mode": "$MODE",
    "return_codes": {
        "replay": int("$replay_rc"),
        "reduce": int("$reduce_rc"),
        "check": int("$check_rc"),
    },
    "pass": int("$check_rc") == 0,
    "artifacts": {
        "accepted_trace": "$ACCEPTED_TRACE_JSON",
        "candidate_trace": "$CANDIDATE_TRACE_JSON",
        "fixture_json": "$FIXTURE_JSON",
        "fixture_md": "$FIXTURE_MD",
        "replay_json": "$REPLAY_JSON",
        "replay_md": "$REPLAY_OUT_MD" if "$SPEC_TRACE_JSONL" else "",
        "spec_summary": "$SPEC_SUMMARY_JSON",
    },
}
Path("$SUMMARY_JSON").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, sort_keys=True))
PY

echo "[oracle:$LABEL] summary=$SUMMARY_JSON"
exit "$check_rc"
