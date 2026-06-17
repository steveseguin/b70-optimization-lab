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


def compact_state(row: dict[str, Any], key: str) -> dict[str, Any] | None:
    state = row.get(key)
    if not isinstance(state, dict):
        return None
    wanted = [
        "num_prompt_tokens",
        "num_output_tokens",
        "num_tokens",
        "num_tokens_with_spec",
        "num_computed_tokens",
        "num_output_placeholders",
        "spec_len",
        "max_tokens",
        "is_prefill_chunk",
        "status",
        "last_output_token_ids",
    ]
    return {name: state.get(name) for name in wanted if name in state}


def state_transition_summary(row: dict[str, Any]) -> dict[str, Any] | None:
    before = compact_state(row, "request_state_before_reject_adjust")
    after_reject = compact_state(row, "request_state_after_reject_adjust")
    after_output = compact_state(row, "request_state_after_output_update")
    if not (before or after_reject or after_output):
        return None

    def get(state: dict[str, Any] | None, key: str) -> Any:
        return state.get(key) if isinstance(state, dict) else None

    return {
        "before": before,
        "after_reject_adjust": after_reject,
        "after_output_update": after_output,
        "num_computed_tokens_delta_reject_adjust": (
            get(after_reject, "num_computed_tokens")
            - get(before, "num_computed_tokens")
            if isinstance(get(before, "num_computed_tokens"), int)
            and isinstance(get(after_reject, "num_computed_tokens"), int)
            else None
        ),
        "num_tokens_delta_output_update": (
            get(after_output, "num_tokens") - get(after_reject, "num_tokens")
            if isinstance(get(after_reject, "num_tokens"), int)
            and isinstance(get(after_output, "num_tokens"), int)
            else None
        ),
        "num_output_tokens_delta_output_update": (
            get(after_output, "num_output_tokens")
            - get(after_reject, "num_output_tokens")
            if isinstance(get(after_reject, "num_output_tokens"), int)
            and isinstance(get(after_output, "num_output_tokens"), int)
            else None
        ),
    }


def accounting_check(
    row: dict[str, Any], transition: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not transition:
        return None
    actual = transition.get("num_computed_tokens_delta_reject_adjust")
    if actual is None:
        return None
    num_rejected = int(row.get("num_rejected") or 0)
    suppressed_count = row.get("num_suppressed_bonus_tokens")
    if suppressed_count is None:
        suppressed_count = 1 if row.get("suppressed_bonus_token_id") is not None else 0
    suppressed_count = int(suppressed_count or 0)
    expected = -(num_rejected + suppressed_count)
    return {
        "expected_computed_delta": expected,
        "actual_computed_delta": actual,
        "num_rejected": num_rejected,
        "num_suppressed_bonus_tokens": suppressed_count,
        "matches": actual == expected,
    }


def load_token_cases(paths: list[Path]) -> dict[str, dict[str, Any]]:
    cases_by_request: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = load_json(path)
        for case in data.get("cases") or []:
            aliases = [
                str(value)
                for value in (case.get("request_id"), case.get("response_id"))
                if value
            ]
            if not aliases:
                continue
            record = {
                "path": str(path),
                "name": case.get("name"),
                "repeat_idx": case.get("repeat_idx"),
                "normalized": case.get("normalized"),
                "output_token_count": case.get("output_token_count"),
                "output_token_ids": case.get("output_token_ids") or [],
                "request_started_at_unix": case.get("request_started_at_unix"),
                "request_finished_at_unix": case.get("request_finished_at_unix"),
                "sha256": case.get("sha256"),
                "request_id": case.get("request_id"),
                "response_id": case.get("response_id"),
                "aliases": aliases,
            }
            for request_id in aliases:
                cases_by_request[request_id] = record
    return cases_by_request


def resolve_token_case(
    req_id: str, cases_by_request: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    if req_id in cases_by_request:
        return {
            "join_method": "exact",
            "matched_request_id": req_id,
            "case": cases_by_request[req_id],
        }

    prefix_matches = [
        (case_req_id, case)
        for case_req_id, case in cases_by_request.items()
        if req_id.startswith(case_req_id + "-")
    ]
    if len(prefix_matches) == 1:
        case_req_id, case = prefix_matches[0]
        return {
            "join_method": "scheduler_prefix",
            "matched_request_id": case_req_id,
            "case": case,
        }

    reverse_prefix_matches = [
        (case_req_id, case)
        for case_req_id, case in cases_by_request.items()
        if case_req_id.startswith(req_id + "-")
    ]
    if len(reverse_prefix_matches) == 1:
        case_req_id, case = reverse_prefix_matches[0]
        return {
            "join_method": "client_prefix",
            "matched_request_id": case_req_id,
            "case": case,
        }

    return None


def summarize_request(
    req_id: str,
    rows: list[dict[str, Any]],
    tokenizer: Any | None,
    token_case_match: dict[str, Any] | None,
) -> dict[str, Any]:
    token_case = token_case_match.get("case") if token_case_match else None
    emitted_sequence: list[int] = []
    generated_sequence: list[int] = []
    suppressed_sequence: list[int] = []
    row_summaries: list[dict[str, Any]] = []
    suppressed_followup_checks: list[dict[str, Any]] = []
    accounting_checks: list[dict[str, Any]] = []

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
            next_scheduled = int_list(next_row.get("scheduled_spec_token_ids"))
            next_generated = int_list(next_row.get("generated_token_ids"))
            next_emitted = int_list(next_row.get("emitted_token_ids"))
            if not next_emitted and next_generated:
                next_emitted = next_generated
            next_first = next_generated[0] if next_generated else None
            next_scheduled_first = next_scheduled[0] if next_scheduled else None
            next_emitted_first = next_emitted[0] if next_emitted else None
            next_num_accepted = int(next_row.get("num_accepted") or 0)
            next_num_rejected = int(next_row.get("num_rejected") or 0)
            followup = {
                "line_no": row.get("_line_no"),
                "next_line_no": next_row.get("_line_no"),
                "suppressed_bonus_token_id": suppressed_int,
                "suppressed_bonus_text": decode_ids(tokenizer, [suppressed_int]),
                "next_scheduled_first_token_id": next_scheduled_first,
                "next_scheduled_first_text": (
                    decode_ids(tokenizer, [next_scheduled_first])
                    if next_scheduled_first is not None
                    else None
                ),
                "next_generated_first_token_id": next_first,
                "next_generated_first_text": (
                    decode_ids(tokenizer, [next_first]) if next_first is not None else None
                ),
                "next_emitted_first_token_id": next_emitted_first,
                "next_emitted_first_text": (
                    decode_ids(tokenizer, [next_emitted_first])
                    if next_emitted_first is not None
                    else None
                ),
                "next_num_accepted": next_num_accepted,
                "next_num_rejected": next_num_rejected,
                "next_schedules_suppressed_bonus": (
                    next_scheduled_first == suppressed_int
                ),
                "next_replays_suppressed_bonus": next_first == suppressed_int,
                "next_accepts_suppressed_bonus": (
                    next_scheduled_first == suppressed_int
                    and next_num_accepted > 0
                    and next_emitted_first == suppressed_int
                ),
                "next_rejects_suppressed_bonus": (
                    next_scheduled_first == suppressed_int
                    and next_num_rejected > 0
                ),
            }
            suppressed_followup_checks.append(followup)

        state_transition = state_transition_summary(row)
        row_accounting_check = accounting_check(row, state_transition)
        if row_accounting_check is not None:
            accounting_checks.append({
                "line_no": row.get("_line_no"),
                **row_accounting_check,
            })

        row_summaries.append({
            "line_no": row.get("_line_no"),
            "ts": row.get("ts"),
            "num_draft_tokens": row.get("num_draft_tokens"),
            "num_accepted": row.get("num_accepted"),
            "num_rejected": row.get("num_rejected"),
            "num_suppressed_bonus_tokens": row.get(
                "num_suppressed_bonus_tokens"
            ),
            "num_tokens_scheduled": row.get("num_tokens_scheduled"),
            "num_computed_tokens": row.get("num_computed_tokens"),
            "num_output_tokens": row.get("num_output_tokens"),
            "scheduled_spec_token_ids": scheduled,
            "scheduled_spec_text": decode_ids(tokenizer, scheduled),
            "generated_token_ids": generated,
            "generated_text": decode_ids(tokenizer, generated),
            "emitted_token_ids": emitted,
            "emitted_text": decode_ids(tokenizer, emitted),
            "new_token_ids_after_stop_check": int_list(
                row.get("new_token_ids_after_stop_check")
            ),
            "suppressed_bonus_token_id": suppressed_int,
            "suppressed_bonus_text": (
                decode_ids(tokenizer, [suppressed_int])
                if suppressed_int is not None
                else None
            ),
            "followup_check": followup,
            "state_transition": state_transition,
            "accounting_check": row_accounting_check,
            "computed_minus_tokens_after_output": (
                state_transition["after_output_update"]["num_computed_tokens"]
                - state_transition["after_output_update"]["num_tokens"]
                if state_transition
                and isinstance(state_transition.get("after_output_update"), dict)
                and isinstance(
                    state_transition["after_output_update"].get("num_computed_tokens"),
                    int,
                )
                and isinstance(
                    state_transition["after_output_update"].get("num_tokens"),
                    int,
                )
                else None
            ),
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
        "suppressed_followup_schedule_mismatches": [
            item for item in suppressed_followup_checks
            if item.get("next_schedules_suppressed_bonus") is False
        ],
        "suppressed_followup_accept_mismatches": [
            item for item in suppressed_followup_checks
            if item.get("next_accepts_suppressed_bonus") is False
        ],
        "accounting_checks": accounting_checks,
        "accounting_mismatches": [
            item for item in accounting_checks if item.get("matches") is False
        ],
        "token_trace_case": token_case,
        "token_trace_join_method": (
            token_case_match.get("join_method") if token_case_match else None
        ),
        "token_trace_matched_request_id": (
            token_case_match.get("matched_request_id") if token_case_match else None
        ),
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
        f"- suppressed schedule mismatches: `{summary['suppressed_schedule_mismatch_count']}`",
        f"- suppressed accept mismatches: `{summary['suppressed_accept_mismatch_count']}`",
        f"- accounting mismatches: `{summary['accounting_mismatch_count']}`",
        "",
        "| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for item in summary["request_summaries"]:
        case = item.get("token_trace_case") or {}
        case_label = case.get("name") or ""
        if case.get("repeat_idx") is not None:
            case_label += f"[{case['repeat_idx']}]"
        join_method = item.get("token_trace_join_method") or ""
        if join_method:
            case_label = f"{case_label} ({join_method})"
        lines.append(
            f"| `{item['req_id']}` | {item['rows']} | {item['draft_tokens']} | "
            f"{item['accepted']} | {item['rejected']} | {item['suppressed_bonus_rows']} | "
            f"`{case_label}` | {len(item['suppressed_followup_mismatches'])} | "
            f"{len(item['suppressed_followup_schedule_mismatches'])} | "
            f"{len(item['suppressed_followup_accept_mismatches'])} | "
            f"{len(item['accounting_mismatches'])} |"
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
                    f"`{mismatch['suppressed_bonus_text']}`, next scheduled "
                    f"`{mismatch['next_scheduled_first_token_id']}` "
                    f"`{mismatch['next_scheduled_first_text']}`, next verifier token was "
                    f"`{mismatch['next_generated_first_token_id']}` "
                    f"`{mismatch['next_generated_first_text']}`, next emitted "
                    f"`{mismatch['next_emitted_first_token_id']}` "
                    f"`{mismatch['next_emitted_first_text']}`."
                ),
            ])
    accounting_mismatches = [
        (item["req_id"], mismatch)
        for item in summary["request_summaries"]
        for mismatch in item["accounting_mismatches"]
    ]
    if accounting_mismatches:
        lines.extend(["", "## Accounting Mismatches", ""])
        for req_id, mismatch in accounting_mismatches:
            lines.append(
                f"- request `{req_id}` line `{mismatch['line_no']}`: "
                f"expected computed delta "
                f"`{mismatch['expected_computed_delta']}` from rejected "
                f"`{mismatch['num_rejected']}` plus suppressed "
                f"`{mismatch['num_suppressed_bonus_tokens']}`, observed "
                f"`{mismatch['actual_computed_delta']}`."
            )
    state_rows = [
        (item["req_id"], row)
        for item in summary["request_summaries"]
        for row in item["row_summaries"]
        if row.get("state_transition")
    ]
    if state_rows:
        lines.extend([
            "",
            "## Request Counter Transitions",
            "",
            "| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for req_id, row in state_rows[:20]:
            transition = row["state_transition"]
            lines.append(
                f"| `{req_id}` | {row.get('line_no')} | "
                f"{row.get('num_tokens_scheduled')} | {row.get('num_accepted')} | "
                f"{row.get('num_rejected')} | "
                f"{transition.get('num_computed_tokens_delta_reject_adjust')} | "
                f"{transition.get('num_output_tokens_delta_output_update')} | "
                f"{transition.get('num_tokens_delta_output_update')} |"
            )
        lines.extend([
            "",
            "Post-output `computed_minus_tokens` is included in the JSON rows.",
            "Values below zero usually mean the next pass may recompute an already",
            "emitted token; values above zero after suppressing a bonus can mean stale",
            "unemitted KV stayed live.",
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
        summarize_request(req_id, req_rows, tokenizer, resolve_token_case(req_id, token_cases))
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
    schedule_mismatch_count = sum(
        len(item["suppressed_followup_schedule_mismatches"])
        for item in request_summaries
    )
    accept_mismatch_count = sum(
        len(item["suppressed_followup_accept_mismatches"])
        for item in request_summaries
    )
    accounting_mismatch_count = sum(
        len(item["accounting_mismatches"]) for item in request_summaries
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
        "suppressed_schedule_mismatch_count": schedule_mismatch_count,
        "suppressed_accept_mismatch_count": accept_mismatch_count,
        "accounting_mismatch_count": accounting_mismatch_count,
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
        "suppressed_schedule_mismatch_count": schedule_mismatch_count,
        "suppressed_accept_mismatch_count": accept_mismatch_count,
        "accounting_mismatch_count": accounting_mismatch_count,
        "out_json": str(args.out_json),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
