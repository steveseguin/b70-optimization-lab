#!/usr/bin/env python3
"""Check reduced Qwen3.6 oracle/spec fixtures.

This is a lightweight regression gate around
``reduce-qwen36-oracle-fixture.py`` output. Use ``--mode exact`` after a
speculative scheduler/KV patch; use ``--mode known-drift`` to verify that the
current minimized failure still describes the expected blocker.

For copy-on-write verifier work, pair ``--mode exact`` with
``--expect-spec-active``. That proves the speculative/verifier path actually
ran while the final token stream still matched the accepted baseline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def mismatch_cases(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        case
        for case in fixture.get("cases") or []
        if isinstance(case, dict) and case.get("status") != "match"
    ]


def mapped_roles(cases: list[dict[str, Any]]) -> list[str]:
    roles: list[str] = []
    for case in cases:
        diff = case.get("first_diff")
        if not isinstance(diff, dict):
            continue
        replay = diff.get("replay_mapping")
        if not isinstance(replay, dict):
            continue
        role = replay.get("emission_role")
        if role:
            roles.append(str(role))
    return roles


def check_replay(
    replay: dict[str, Any],
    errors: list[str],
    *,
    allow_accounting_mismatch: bool = False,
) -> None:
    if int(replay.get("malformed_rows") or 0) != 0:
        fail(errors, "replay contains malformed rows")
    if int(replay.get("joined_requests") or 0) != int(replay.get("requests") or 0):
        fail(errors, "replay did not join every request to a token case")
    accounting_mismatches = int(replay.get("accounting_mismatch_count") or 0)
    if accounting_mismatches != 0 and not allow_accounting_mismatch:
        fail(errors, "replay accounting mismatches are present")
    if int(replay.get("suppressed_followup_mismatch_count") or 0) != 0:
        fail(errors, "suppressed follow-up mismatches are present")


def load_spec_summary(fixture: dict[str, Any], path: Path | None) -> dict[str, Any] | None:
    if path is not None:
        data = load_json(path)
        if isinstance(data, dict) and isinstance(data.get("spec_summary"), dict):
            return data["spec_summary"]
        return data if isinstance(data, dict) else None
    summary = fixture.get("spec_summary")
    return summary if isinstance(summary, dict) else None


def spec_totals(summary: dict[str, Any] | None) -> dict[str, Any]:
    totals: dict[str, Any] = {
        "rows": 0,
        "requests": 0,
        "draft_tokens": 0,
        "accepted": 0,
        "rejected": 0,
        "accept_rate_pct": None,
        "trace_count": 0,
    }
    if not summary:
        return totals
    traces = summary.get("traces")
    if not isinstance(traces, list):
        return totals
    totals["trace_count"] = len(traces)
    request_ids: set[str] = set()
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        totals["rows"] += int(trace.get("rows") or 0)
        totals["draft_tokens"] += int(trace.get("draft_tokens") or 0)
        totals["accepted"] += int(trace.get("accepted") or 0)
        totals["rejected"] += int(trace.get("rejected") or 0)
        ids = trace.get("request_ids")
        if isinstance(ids, list):
            request_ids.update(str(item) for item in ids)
        else:
            totals["requests"] += int(trace.get("requests") or 0)
    if request_ids:
        totals["requests"] = len(request_ids)
    if totals["draft_tokens"]:
        totals["accept_rate_pct"] = (
            float(totals["accepted"]) * 100.0 / float(totals["draft_tokens"])
        )
    return totals


def check_spec_summary(
    fixture: dict[str, Any],
    summary: dict[str, Any] | None,
    args: argparse.Namespace,
    errors: list[str],
) -> dict[str, Any]:
    totals = spec_totals(summary)
    needs_summary = (
        args.expect_spec_active
        or args.min_draft_tokens > 0
        or args.min_accepted_tokens > 0
        or args.min_accept_rate_pct is not None
        or args.require_spec_join
    )
    if needs_summary and not summary:
        fail(errors, "spec summary is required but missing")
        return totals

    if args.expect_spec_active:
        if totals["draft_tokens"] <= 0:
            fail(errors, "expected speculative draft tokens, found none")
        if totals["accepted"] <= 0:
            fail(errors, "expected accepted speculative tokens, found none")
    if totals["draft_tokens"] < args.min_draft_tokens:
        fail(
            errors,
            f"expected at least {args.min_draft_tokens} draft tokens, "
            f"found {totals['draft_tokens']}",
        )
    if totals["accepted"] < args.min_accepted_tokens:
        fail(
            errors,
            f"expected at least {args.min_accepted_tokens} accepted draft tokens, "
            f"found {totals['accepted']}",
        )
    if args.min_accept_rate_pct is not None:
        rate = totals["accept_rate_pct"]
        if rate is None or rate < args.min_accept_rate_pct:
            fail(
                errors,
                f"expected accept_rate_pct >= {args.min_accept_rate_pct}, found {rate}",
            )

    if args.require_spec_join and summary:
        joinability = summary.get("joinability")
        if not isinstance(joinability, dict):
            fail(errors, "spec summary joinability is missing")
        else:
            if joinability.get("request_id_join_possible") is not True:
                fail(errors, "spec summary request-id join is not possible")
            trace_count = int(joinability.get("trace_request_count") or 0)
            artifact_count = int(joinability.get("artifact_request_count") or 0)
            case_count = int(fixture.get("case_count") or 0)
            if trace_count != artifact_count:
                fail(
                    errors,
                    f"spec trace/artifact request count mismatch: {trace_count} != {artifact_count}",
                )
            if case_count and artifact_count != case_count:
                fail(
                    errors,
                    f"spec artifact request count {artifact_count} != fixture case count {case_count}",
                )
    return totals


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--replay-json", type=Path)
    parser.add_argument(
        "--spec-summary",
        type=Path,
        help="Optional spec summary JSON. Defaults to fixture.spec_summary when present.",
    )
    parser.add_argument(
        "--mode",
        choices=("exact", "known-drift"),
        default="exact",
        help="exact requires no mismatches; known-drift checks the current minimized failure shape.",
    )
    parser.add_argument("--expected-mismatches", type=int, default=0)
    parser.add_argument(
        "--expected-roles",
        default="",
        help="Comma-separated expected emission roles for known-drift mode.",
    )
    parser.add_argument(
        "--expect-spec-active",
        action="store_true",
        help="Require speculative draft and accepted-token activity in the spec summary.",
    )
    parser.add_argument("--min-draft-tokens", type=int, default=0)
    parser.add_argument("--min-accepted-tokens", type=int, default=0)
    parser.add_argument("--min-accept-rate-pct", type=float)
    parser.add_argument(
        "--require-spec-join",
        action="store_true",
        help="Require spec trace request IDs to join back to every fixture case.",
    )
    parser.add_argument(
        "--allow-replay-accounting-mismatch",
        action="store_true",
        help=(
            "Allow replay accounting-only mismatches. This is for token-exact "
            "runs where the trace accounting is known noisy; generated-token "
            "mismatches and suppressed follow-up mismatches still fail."
        ),
    )
    args = parser.parse_args()

    fixture = load_json(args.fixture)
    errors: list[str] = []
    cases = fixture.get("cases") or []
    mismatches = mismatch_cases(fixture)
    mismatch_count = int(fixture.get("mismatch_count") or 0)

    if not isinstance(cases, list) or not cases:
        fail(errors, "fixture has no cases")
    if mismatch_count != len(mismatches):
        fail(
            errors,
            f"fixture mismatch_count={mismatch_count} does not match mismatched cases={len(mismatches)}",
        )

    if args.replay_json:
        check_replay(
            load_json(args.replay_json),
            errors,
            allow_accounting_mismatch=args.allow_replay_accounting_mismatch,
        )
    spec_summary = load_spec_summary(fixture, args.spec_summary)
    spec = check_spec_summary(fixture, spec_summary, args, errors)

    if args.mode == "exact":
        if fixture.get("exact_match_all") is not True:
            fail(errors, "fixture is not exact_match_all=true")
        if mismatch_count != 0:
            fail(errors, f"expected 0 mismatches, found {mismatch_count}")
    else:
        if fixture.get("exact_match_all") is not False:
            fail(errors, "known-drift mode expected exact_match_all=false")
        if mismatch_count != args.expected_mismatches:
            fail(
                errors,
                f"expected {args.expected_mismatches} mismatches, found {mismatch_count}",
            )
        expected_roles = [
            role.strip()
            for role in args.expected_roles.split(",")
            if role.strip()
        ]
        roles = mapped_roles(mismatches)
        if expected_roles and sorted(roles) != sorted(expected_roles):
            fail(
                errors,
                f"expected roles {expected_roles}, found {roles}",
            )
        for case in mismatches:
            diff = case.get("first_diff")
            if not isinstance(diff, dict):
                fail(errors, f"{case.get('name')} has no first_diff")
                continue
            replay = diff.get("replay_mapping")
            if not isinstance(replay, dict) or replay.get("status") != "mapped":
                fail(errors, f"{case.get('name')} is not mapped to a replay row")

    result = {
        "fixture": str(args.fixture),
        "mode": args.mode,
        "case_count": len(cases) if isinstance(cases, list) else 0,
        "mismatch_count": mismatch_count,
        "roles": mapped_roles(mismatches),
        "spec": spec,
        "ok": not errors,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
