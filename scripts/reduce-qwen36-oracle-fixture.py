#!/usr/bin/env python3
"""Reduce Qwen3.6 oracle/spec drift artifacts into a compact fixture.

The speculation path is only useful if the verifier output is byte-for-byte
identical to the accepted baseline. This helper compares two completion trace
artifacts case-by-case, records the first token divergence, and writes a small
JSON/Markdown packet that can drive future regression tests or upstream repros.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cases_by_name(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError("completion artifact must contain a cases list")
    out: dict[str, dict[str, Any]] = {}
    for case in cases:
        name = str(case.get("name") or "")
        if not name:
            raise ValueError("case without a name")
        out[name] = case
    return out


def int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    return [int(item) for item in value]


def load_tokenizer(path: str | None) -> Any | None:
    if not path:
        return None
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(path, trust_remote_code=True)


def decode_ids(tokenizer: Any | None, token_ids: list[int]) -> str | None:
    if tokenizer is None:
        return None
    return tokenizer.decode(token_ids, skip_special_tokens=False)


def first_diff_index(left: list[int], right: list[int]) -> int | None:
    for idx, (left_id, right_id) in enumerate(zip(left, right)):
        if left_id != right_id:
            return idx
    if len(left) != len(right):
        return min(len(left), len(right))
    return None


def token_window(tokens: list[int], index: int | None, radius: int) -> dict[str, Any]:
    if index is None:
        return {"start": None, "end": None, "token_ids": []}
    start = max(0, index - radius)
    end = min(len(tokens), index + radius + 1)
    return {"start": start, "end": end, "token_ids": tokens[start:end]}


def summarize_spec_summary(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    traces = data.get("traces")
    if not isinstance(traces, list) or not traces:
        return None
    compact_traces = []
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        compact_traces.append(
            {
                "path": trace.get("path"),
                "rows": trace.get("rows"),
                "requests": trace.get("requests"),
                "draft_tokens": trace.get("draft_tokens"),
                "accepted": trace.get("accepted"),
                "rejected": trace.get("rejected"),
                "accept_rate_pct": trace.get("accept_rate_pct"),
                "full_accept_rows": trace.get("full_accept_rows"),
                "full_reject_rows": trace.get("full_reject_rows"),
                "max_full_accept_streak": trace.get("max_full_accept_streak"),
                "request_ids": trace.get("request_ids"),
            }
        )
    return {
        "traces": compact_traces,
        "joinability": data.get("joinability"),
    }


def replay_by_case(data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for request in data.get("request_summaries") or []:
        if not isinstance(request, dict):
            continue
        case = request.get("token_trace_case")
        if not isinstance(case, dict):
            continue
        name = case.get("name")
        if name:
            out[str(name)] = request
    return out


def locate_replay_emission(
    *,
    candidate_ids: list[int],
    first_diff: int | None,
    replay_request: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if first_diff is None or not replay_request:
        return None
    emitted = int_list(replay_request.get("emitted_token_ids_from_trace"))
    if not emitted:
        return None

    start_offset = None
    for idx in range(0, max(0, len(candidate_ids) - len(emitted)) + 1):
        if candidate_ids[idx : idx + len(emitted)] == emitted:
            start_offset = idx
            break
    if start_offset is None:
        return {
            "status": "trace_emitted_sequence_not_found_in_candidate",
            "request_id": replay_request.get("req_id"),
        }
    if first_diff < start_offset or first_diff >= start_offset + len(emitted):
        return {
            "status": "first_diff_outside_trace_emitted_sequence",
            "request_id": replay_request.get("req_id"),
            "trace_start_output_index": start_offset,
        }

    rel = first_diff - start_offset
    cursor = 0
    for row in replay_request.get("row_summaries") or []:
        row_emitted = int_list(row.get("emitted_token_ids"))
        row_len = len(row_emitted)
        if rel < cursor + row_len:
            pos = rel - cursor
            accepted = int(row.get("num_accepted") or 0)
            rejected = int(row.get("num_rejected") or 0)
            scheduled = int_list(row.get("scheduled_spec_token_ids"))
            generated = int_list(row.get("generated_token_ids"))
            return {
                "status": "mapped",
                "request_id": replay_request.get("req_id"),
                "trace_start_output_index": start_offset,
                "row_line_no": row.get("line_no"),
                "position_in_row": pos,
                "num_accepted": accepted,
                "num_rejected": rejected,
                "scheduled_spec_token_ids": scheduled,
                "generated_token_ids": generated,
                "emitted_token_ids": row_emitted,
                "emission_role": (
                    "verifier_bonus_after_full_accept"
                    if rejected == 0 and accepted > 0 and pos >= accepted
                    else "replacement_after_reject"
                    if rejected > 0
                    else "accepted_draft"
                    if pos < accepted
                    else "unknown"
                ),
            }
        cursor += row_len
    return {
        "status": "first_diff_not_mapped_to_row",
        "request_id": replay_request.get("req_id"),
        "trace_start_output_index": start_offset,
    }


def build_fixture(
    *,
    accepted_path: Path,
    candidate_path: Path,
    spec_summary_path: Path | None,
    replay_path: Path | None,
    tokenizer_path: str | None,
    window_radius: int,
) -> dict[str, Any]:
    accepted = load_json(accepted_path)
    candidate = load_json(candidate_path)
    tokenizer = load_tokenizer(tokenizer_path)
    accepted_cases = cases_by_name(accepted)
    candidate_cases = cases_by_name(candidate)
    replay_cases = replay_by_case(load_json(replay_path)) if replay_path else {}

    names = sorted(set(accepted_cases) | set(candidate_cases))
    fixture_cases = []
    mismatch_count = 0

    for name in names:
        a = accepted_cases.get(name)
        b = candidate_cases.get(name)
        if a is None or b is None:
            mismatch_count += 1
            fixture_cases.append(
                {
                    "name": name,
                    "status": "missing_case",
                    "accepted_present": a is not None,
                    "candidate_present": b is not None,
                }
            )
            continue

        a_ids = int_list(a.get("output_token_ids"))
        b_ids = int_list(b.get("output_token_ids"))
        diff = first_diff_index(a_ids, b_ids)
        exact = diff is None and a.get("text") == b.get("text")
        if not exact:
            mismatch_count += 1

        a_window = token_window(a_ids, diff, window_radius)
        b_window = token_window(b_ids, diff, window_radius)
        prompt = str(a.get("prompt") or "")
        prompt_match = a.get("prompt_sha256") == b.get("prompt_sha256")
        first_diff = None
        if diff is not None:
            a_token = a_ids[diff] if diff < len(a_ids) else None
            b_token = b_ids[diff] if diff < len(b_ids) else None
            first_diff = {
                "index": diff,
                "accepted_token_id": a_token,
                "candidate_token_id": b_token,
                "accepted_token_text": (
                    decode_ids(tokenizer, [a_token]) if a_token is not None else None
                ),
                "candidate_token_text": (
                    decode_ids(tokenizer, [b_token]) if b_token is not None else None
                ),
                "accepted_window": {
                    **a_window,
                    "text": decode_ids(tokenizer, a_window["token_ids"]),
                },
                "candidate_window": {
                    **b_window,
                    "text": decode_ids(tokenizer, b_window["token_ids"]),
                },
            }
            replay_mapping = locate_replay_emission(
                candidate_ids=b_ids,
                first_diff=diff,
                replay_request=replay_cases.get(name),
            )
            if replay_mapping is not None:
                first_diff["replay_mapping"] = replay_mapping

        fixture_cases.append(
            {
                "name": name,
                "status": "match" if exact else "mismatch",
                "prompt_sha256": a.get("prompt_sha256") or sha256_text(prompt),
                "prompt_match": prompt_match,
                "prompt_token_count": a.get("prompt_token_count"),
                "prompt_token_ids_head": a.get("prompt_token_ids_head"),
                "prompt_token_ids_tail": a.get("prompt_token_ids_tail"),
                "prompt": prompt,
                "accepted": {
                    "response_id": a.get("response_id"),
                    "text_sha256": a.get("text_sha256") or sha256_text(str(a.get("text") or "")),
                    "text": a.get("text"),
                    "output_token_count": len(a_ids),
                    "output_token_ids": a_ids,
                },
                "candidate": {
                    "response_id": b.get("response_id"),
                    "text_sha256": b.get("text_sha256") or sha256_text(str(b.get("text") or "")),
                    "text": b.get("text"),
                    "output_token_count": len(b_ids),
                    "output_token_ids": b_ids,
                },
                "first_diff": first_diff,
            }
        )

    spec_summary = None
    if spec_summary_path is not None:
        spec_summary = summarize_spec_summary(load_json(spec_summary_path))

    return {
        "accepted_path": str(accepted_path),
        "candidate_path": str(candidate_path),
        "spec_summary_path": str(spec_summary_path) if spec_summary_path else None,
        "replay_path": str(replay_path) if replay_path else None,
        "tokenizer_path": tokenizer_path,
        "case_count": len(names),
        "mismatch_count": mismatch_count,
        "exact_match_all": mismatch_count == 0,
        "spec_summary": spec_summary,
        "cases": fixture_cases,
        "next_actions": [
            "Use this fixture as the token-parity gate for any speculative scheduler/KV patch.",
            "First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.",
            "If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.",
        ],
    }


def write_markdown(path: Path, fixture: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 Oracle k=1 Drift Fixture",
        "",
        f"- Accepted: `{fixture['accepted_path']}`",
        f"- Candidate: `{fixture['candidate_path']}`",
        f"- Exact match all: `{fixture['exact_match_all']}`",
        f"- Mismatches: `{fixture['mismatch_count']}` / `{fixture['case_count']}`",
        "",
    ]
    spec = fixture.get("spec_summary") or {}
    traces = spec.get("traces") or []
    if traces:
        trace = traces[0]
        lines.extend(
            [
                "## Scheduler Summary",
                "",
                f"- Rows: `{trace.get('rows')}`",
                f"- Requests: `{trace.get('requests')}`",
                f"- Draft tokens: `{trace.get('draft_tokens')}`",
                f"- Accepted: `{trace.get('accepted')}`",
                f"- Rejected: `{trace.get('rejected')}`",
                f"- Accept rate: `{trace.get('accept_rate_pct')}`",
                f"- Full accept rows: `{trace.get('full_accept_rows')}`",
                f"- Full reject rows: `{trace.get('full_reject_rows')}`",
                "",
            ]
        )
    lines.extend(["## Case Diffs", ""])
    for case in fixture["cases"]:
        lines.append(f"### {case['name']}")
        lines.append("")
        lines.append(f"- Status: `{case['status']}`")
        if case["status"] == "missing_case":
            lines.append(f"- Accepted present: `{case['accepted_present']}`")
            lines.append(f"- Candidate present: `{case['candidate_present']}`")
            lines.append("")
            continue
        diff = case.get("first_diff")
        if diff is None:
            lines.append("- First diff: none")
        else:
            lines.append(f"- First diff index: `{diff['index']}`")
            lines.append(
                "- Accepted token: "
                f"`{diff['accepted_token_id']}` `{diff['accepted_token_text']}`"
            )
            lines.append(
                "- Candidate token: "
                f"`{diff['candidate_token_id']}` `{diff['candidate_token_text']}`"
            )
            lines.append(f"- Accepted window: `{diff['accepted_window']['text']}`")
            lines.append(f"- Candidate window: `{diff['candidate_window']['text']}`")
            replay = diff.get("replay_mapping")
            if replay:
                lines.append(f"- Replay mapping: `{replay.get('status')}`")
                if replay.get("status") == "mapped":
                    lines.append(f"  - Request: `{replay.get('request_id')}`")
                    lines.append(f"  - Trace row: `{replay.get('row_line_no')}`")
                    lines.append(f"  - Position in row: `{replay.get('position_in_row')}`")
                    lines.append(f"  - Emission role: `{replay.get('emission_role')}`")
                    lines.append(
                        f"  - Scheduled: `{replay.get('scheduled_spec_token_ids')}`"
                    )
                    lines.append(
                        f"  - Generated: `{replay.get('generated_token_ids')}`"
                    )
        lines.append("")
    lines.extend(["## Next Actions", ""])
    for action in fixture.get("next_actions", []):
        lines.append(f"- {action}")
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accepted", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--spec-summary", type=Path)
    parser.add_argument("--replay-json", type=Path)
    parser.add_argument("--tokenizer", default=None)
    parser.add_argument("--window-radius", type=int, default=8)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()

    fixture = build_fixture(
        accepted_path=args.accepted,
        candidate_path=args.candidate,
        spec_summary_path=args.spec_summary,
        replay_path=args.replay_json,
        tokenizer_path=args.tokenizer,
        window_radius=args.window_radius,
    )
    args.output_json.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    if args.output_md:
        write_markdown(args.output_md, fixture)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md) if args.output_md else None,
                "exact_match_all": fixture["exact_match_all"],
                "mismatch_count": fixture["mismatch_count"],
                "case_count": fixture["case_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if fixture["exact_match_all"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
