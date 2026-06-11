#!/usr/bin/env python3
"""Replay and inspect Qwen3.6 speculative scheduler trace rows.

This script does not run the model. It reconstructs the token increments visible
in vLLM scheduler JSONL traces, groups rows by request id, and flags suspicious
state transitions. The first target is the no-bonus diagnostic: when a
full-accept row suppresses the verifier bonus token, the next verifier step for
that request should normally regenerate that suppressed token. If it does not,
the speculative path has likely advanced or exposed stale state incorrectly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_trace(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        row["_line_no"] = line_no
        rows.append(row)
    return rows, malformed


def decode_ids(tokenizer: Any | None, token_ids: list[int]) -> str | None:
    if tokenizer is None:
        return None
    return tokenizer.decode(token_ids, skip_special_tokens=False)


def int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    return [int(item) for item in value]


def load_token_cases(paths: list[Path]) -> dict[str, dict[str, Any]]:
    cases_by_request: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = load_json(path)
        for case in data.get("cases") or []:
            request_id = case.get("request_id") or case.get("response_id")
            if request_id:
                cases_by_request[str(request_id)] = {
                    "path": str(path),
                    "name": case.get("name"),
                    "repeat_idx": case.get("repeat_idx"),
                    "normalized": case.get("normalized"),
                    "output_token_count": case.get("output_token_count"),
                    "output_token_ids": case.get("output_token_ids") or [],
                    "request_started_at_unix": case.get("request_started_at_unix"),
                    "request_finished_at_unix": case.get("request_finished_at_unix"),
                    "sha256": case.get("sha256"),
                }
    return cases_by_request


def summarize_request(
    req_id: str,
    rows: list[dict[str, Any]],
    tokenizer: Any | None,
    token_case: dict[str, Any] | None,
) -> dict[str, Any]:
    emitted_sequence: list[int] = []
    generated_sequence: list[int] = []
    suppressed_sequence: list[int] = []
    row_summaries: list[dict[str, Any]] = []
    suppressed_followup_checks: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        scheduled = int_list(row.get("scheduled_spec_token_ids"))
        generated = int_list(row.get("generated_token_ids"))
        emitted = int_list(row.get("emitted_token_ids"))
        if not emitted and generated:
            emitted = generated
        suppressed = row.get("suppressed_bonus_token_id")
        suppressed_int = int(suppressed) if suppressed is not None else None

        emitted_sequence.extend(emitted)
        generated_sequence.extend(generated)
        if suppressed_int is not None:
            suppressed_sequence.append(suppressed_int)

        next_row = rows[index + 1] if index + 1 < len(rows) else None
        followup = None
        if suppressed_int is not None and next_row is not None:
            next_generated = int_list(next_row.get("generated_token_ids"))
            next_first = next_generated[0] if next_generated else None
            followup = {
                "line_no": row.get("_line_no"),
                "next_line_no": next_row.get("_line_no"),
                "suppressed_bonus_token_id": suppressed_int,
                "suppressed_bonus_text": decode_ids(tokenizer, [suppressed_int]),
                "next_generated_first_token_id": next_first,
                "next_generated_first_text": (
                    decode_ids(tokenizer, [next_first]) if next_first is not None else None
                ),
                "next_replays_suppressed_bonus": next_first == suppressed_int,
            }
            suppressed_followup_checks.append(followup)

        row_summaries.append({
            "line_no": row.get("_line_no"),
            "ts": row.get("ts"),
            "num_draft_tokens": row.get("num_draft_tokens"),
            "num_accepted": row.get("num_accepted"),
            "num_rejected": row.get("num_rejected"),
            "num_computed_tokens": row.get("num_computed_tokens"),
            "num_output_tokens": row.get("num_output_tokens"),
            "scheduled_spec_token_ids": scheduled,
            "scheduled_spec_text": decode_ids(tokenizer, scheduled),
            "generated_token_ids": generated,
            "generated_text": decode_ids(tokenizer, generated),
            "emitted_token_ids": emitted,
            "emitted_text": decode_ids(tokenizer, emitted),
            "suppressed_bonus_token_id": suppressed_int,
            "suppressed_bonus_text": (
                decode_ids(tokenizer, [suppressed_int])
                if suppressed_int is not None
                else None
            ),
            "followup_check": followup,
        })

    token_case_output = int_list((token_case or {}).get("output_token_ids"))
    traced_emitted_is_prefix = None
    if token_case_output:
        traced_emitted_is_prefix = token_case_output[:len(emitted_sequence)] == emitted_sequence

    return {
        "req_id": req_id,
        "rows": len(rows),
        "first_ts": min((row.get("ts") for row in rows if row.get("ts") is not None), default=None),
        "last_ts": max((row.get("ts") for row in rows if row.get("ts") is not None), default=None),
        "draft_tokens": sum(int(row.get("num_draft_tokens") or 0) for row in rows),
        "accepted": sum(int(row.get("num_accepted") or 0) for row in rows),
        "rejected": sum(int(row.get("num_rejected") or 0) for row in rows),
        "suppressed_bonus_rows": sum(
            1 for row in rows if row.get("suppressed_bonus_token_id") is not None
        ),
        "emitted_token_ids_from_trace": emitted_sequence,
        "emitted_text_from_trace": decode_ids(tokenizer, emitted_sequence),
        "generated_token_ids_from_trace": generated_sequence,
        "generated_text_from_trace": decode_ids(tokenizer, generated_sequence),
        "suppressed_bonus_token_ids": suppressed_sequence,
        "suppressed_bonus_text": decode_ids(tokenizer, suppressed_sequence),
        "suppressed_followup_checks": suppressed_followup_checks,
        "suppressed_followup_mismatches": [
            item for item in suppressed_followup_checks
            if item.get("next_replays_suppressed_bonus") is False
        ],
        "token_trace_case": token_case,
        "traced_emitted_is_token_trace_prefix": traced_emitted_is_prefix,
        "row_summaries": row_summaries,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Qwen3.6 Spec Trace Replay",
        "",
        f"- trace: `{summary['trace_path']}`",
        f"- rows: `{summary['rows']}`",
        f"- malformed rows: `{summary['malformed_rows']}`",
        f"- requests: `{summary['requests']}`",
        f"- suppressed follow-up mismatches: `{summary['suppressed_followup_mismatch_count']}`",
        "",
        "| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | follow-up mismatches |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for item in summary["request_summaries"]:
        case = item.get("token_trace_case") or {}
        case_label = case.get("name") or ""
        if case.get("repeat_idx") is not None:
            case_label += f"[{case['repeat_idx']}]"
        lines.append(
            f"| `{item['req_id']}` | {item['rows']} | {item['draft_tokens']} | "
            f"{item['accepted']} | {item['rejected']} | {item['suppressed_bonus_rows']} | "
            f"`{case_label}` | {len(item['suppressed_followup_mismatches'])} |"
        )

    mismatches = [
        (item["req_id"], mismatch)
        for item in summary["request_summaries"]
        for mismatch in item["suppressed_followup_mismatches"]
    ]
    if mismatches:
        lines.extend(["", "## Suppressed Follow-Up Mismatches", ""])
        for req_id, mismatch in mismatches:
            lines.extend([
                f"- request `{req_id}` line `{mismatch['line_no']}` -> `{mismatch['next_line_no']}`:",
                (
                    f"  suppressed `{mismatch['suppressed_bonus_token_id']}` "
                    f"`{mismatch['suppressed_bonus_text']}` but next verifier token was "
                    f"`{mismatch['next_generated_first_token_id']}` "
                    f"`{mismatch['next_generated_first_text']}`"
                ),
            ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-jsonl", type=Path, required=True)
    parser.add_argument("--tokenizer")
    parser.add_argument("--token-trace-json", type=Path, action="append", default=[])
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args()

    tokenizer = None
    if args.tokenizer:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)

    rows, malformed = load_trace(args.trace_jsonl)
    by_req: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        req_id = str(row.get("req_id") or "")
        by_req.setdefault(req_id, []).append(row)

    token_cases = load_token_cases(args.token_trace_json)
    request_summaries = [
        summarize_request(req_id, req_rows, tokenizer, token_cases.get(req_id))
        for req_id, req_rows in by_req.items()
    ]
    request_summaries.sort(
        key=lambda item: (
            len(item["suppressed_followup_mismatches"]),
            item["draft_tokens"],
            item["rows"],
        ),
        reverse=True,
    )

    mismatch_count = sum(
        len(item["suppressed_followup_mismatches"]) for item in request_summaries
    )
    joined_requests = sum(1 for item in request_summaries if item.get("token_trace_case"))
    summary = {
        "trace_path": str(args.trace_jsonl),
        "token_trace_paths": [str(path) for path in args.token_trace_json],
        "rows": len(rows),
        "malformed_rows": malformed,
        "requests": len(by_req),
        "joined_requests": joined_requests,
        "suppressed_followup_mismatch_count": mismatch_count,
        "request_summaries": request_summaries,
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summary, indent=2) + "\n")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_markdown(summary))

    print(json.dumps({
        "trace": str(args.trace_jsonl),
        "rows": len(rows),
        "requests": len(by_req),
        "joined_requests": joined_requests,
        "suppressed_followup_mismatch_count": mismatch_count,
        "out_json": str(args.out_json),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
