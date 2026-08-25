#!/usr/bin/env python3
"""Fail-closed context/retrieval benchmark compatible with the strict runner.

The generic realistic-suite benchmark correctly measures throughput and cache
freshness, but it does not understand the context suite's per-row retrieval
markers.  This helper preserves its request and metric implementation while
stopping before the next depth as soon as a marker, token-count, freshness, or
metric-window gate fails.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
BASE_HELPER = REPO / "scripts/bench-openai-realistic-suite.py"


def load_base_helper() -> Any:
    spec = importlib.util.spec_from_file_location("nd_realistic_bench", BASE_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BASE_HELPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_context_row(
    row: dict[str, Any], prompt: dict[str, Any], metric_tokens: int
) -> list[str]:
    failures: list[str] = []
    expected = prompt["expected_prefix"]
    preview = row.get("text_preview")
    if not isinstance(preview, str) or not preview.lstrip().startswith(expected):
        failures.append("retrieval-marker-mismatch")
    if row.get("prompt_tokens") != prompt["actual_prompt_tokens"]:
        failures.append("actual-prompt-token-count-mismatch")
    if row.get("cached_tokens") != 0:
        failures.append("cached-tokens-not-zero")
    if not isinstance(row.get("completion_tokens"), int) or row["completion_tokens"] < metric_tokens:
        failures.append("completion-shorter-than-metric-window")
    if not isinstance(row.get("stream_token_id_count"), int) or row["stream_token_id_count"] < metric_tokens:
        failures.append("token-id-window-incomplete")
    if not isinstance(row.get("tok_s_1_100_intervals_after_ttft"), (int, float)):
        failures.append("conventional-decode-metric-missing")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-mode", choices=("chat",), required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, required=True)
    parser.add_argument("--metric-tokens", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prompt-id", action="append", default=[])
    parser.add_argument("--return-token-ids", action="store_true")
    parser.add_argument("--request-extra-json", default="{}")
    parser.add_argument("--require-natural-eos", action="store_true")
    args = parser.parse_args()

    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    semantics = suite.get("evidence_semantics")
    if (
        suite.get("suite_id") != "qwen38-b2dd-tp1-context-sentinels-v1"
        or not isinstance(semantics, dict)
        or semantics.get("fills_exact_active_context_axis") is not False
        or semantics.get("input_32000_fills_active_context_32768") is not False
    ):
        raise SystemExit("refusing a suite without the frozen supporting-only semantics")
    request_extra = json.loads(args.request_extra_json)
    if not isinstance(request_extra, dict) or request_extra.get("ignore_eos") is not True:
        raise SystemExit("context sentinels require ignore_eos=true")
    if args.require_natural_eos or not args.return_token_ids:
        raise SystemExit("context sentinels require token IDs and fixed-length output")

    prompts = suite.get("prompts")
    if not isinstance(prompts, list):
        raise SystemExit("context suite prompts are missing")
    if args.prompt_id:
        requested = set(args.prompt_id)
        prompts = [prompt for prompt in prompts if prompt.get("id") in requested]
        found = {prompt.get("id") for prompt in prompts}
        if found != requested:
            raise SystemExit(f"unknown prompt IDs: {sorted(requested - found)}")

    base = load_base_helper()
    rows: list[dict[str, Any]] = []
    first_failure: dict[str, Any] | None = None
    for index, prompt in enumerate(prompts):
        row = base.post_stream(
            base_url=args.base_url,
            model=args.model,
            prompt=prompt["prompt"],
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            api_mode=args.api_mode,
            seed=args.seed,
            request_extra=request_extra,
            return_token_ids=True,
            system_prompt=None,
            request_id=base.safe_request_id(
                f"context-{suite['suite_id']}-{index:02d}-{prompt['id']}"
            ),
        )
        row["prompt_index"] = index
        row["prompt_id"] = prompt["id"]
        row["prompt_sha256"] = hashlib.sha256(
            prompt["prompt"].encode("utf-8")
        ).hexdigest()
        row["requested_prompt_tokens"] = prompt["requested_prompt_tokens"]
        row["expected_actual_prompt_tokens"] = prompt["actual_prompt_tokens"]
        row["expected_prefix"] = prompt["expected_prefix"]
        row["cached_tokens"] = base.cached_tokens(row)
        legacy, conventional = base.event_window_rates(
            row.get("token_id_offsets_s") or [], args.metric_tokens
        )
        row["tok_s_1_100_after_ttft"] = legacy
        row["tok_s_1_100_after_ttft_legacy_inclusive_events"] = legacy
        row["tok_s_1_100_intervals_after_ttft"] = conventional
        failures = validate_context_row(row, prompt, args.metric_tokens)
        row["context_gate_passed"] = not failures
        row["context_gate_failures"] = failures
        rows.append(row)
        if failures:
            first_failure = {"prompt_id": prompt["id"], "reasons": failures}
            break

    conventional_values = [
        float(row["tok_s_1_100_intervals_after_ttft"])
        for row in rows
        if isinstance(row.get("tok_s_1_100_intervals_after_ttft"), (int, float))
    ]
    passed = first_failure is None and len(rows) == len(prompts)
    result = {
        "run_identity": {
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "base_url": args.base_url,
            "model": args.model,
            "api_mode": args.api_mode,
            "suite_path": str(args.suite),
            "suite_id": suite["suite_id"],
            "prompt_count_planned": len(prompts),
            "max_tokens": args.max_tokens,
            "metric_tokens": args.metric_tokens,
            "selected_prompt_ids": args.prompt_id,
            "evidence_kind": "serving-input-probe",
            "fills_exact_active_context_axis": False,
        },
        "realistic_final_gate": {
            "passed": passed,
            "classification": "supporting-context-probe",
            "cached_tokens_all_zero": all(row.get("cached_tokens") == 0 for row in rows),
            "metric_token_id_events_at_least_window": all(
                isinstance(row.get("stream_token_id_count"), int)
                and row["stream_token_id_count"] >= args.metric_tokens
                for row in rows
            ),
        },
        "context_retrieval_gate": {
            "passed": passed,
            "stopped_on_first_failure": first_failure is not None,
            "first_failure": first_failure,
            "rows_completed": len(rows),
            "rows_planned": len(prompts),
            "fills_exact_active_context_axis": False,
            "input_32000_fills_active_context_32768": False,
        },
        "summary": {
            "tok_s_1_100_intervals_after_ttft": base.stats(conventional_values)
        },
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
