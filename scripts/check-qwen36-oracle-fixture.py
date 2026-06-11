#!/usr/bin/env python3
"""Check reduced Qwen3.6 oracle/spec fixtures.

This is a lightweight regression gate around
``reduce-qwen36-oracle-fixture.py`` output. Use ``--mode exact`` after a
speculative scheduler/KV patch; use ``--mode known-drift`` to verify that the
current minimized failure still describes the expected blocker.
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


def check_replay(replay: dict[str, Any], errors: list[str]) -> None:
    if int(replay.get("malformed_rows") or 0) != 0:
        fail(errors, "replay contains malformed rows")
    if int(replay.get("joined_requests") or 0) != int(replay.get("requests") or 0):
        fail(errors, "replay did not join every request to a token case")
    if int(replay.get("accounting_mismatch_count") or 0) != 0:
        fail(errors, "replay accounting mismatches are present")
    if int(replay.get("suppressed_followup_mismatch_count") or 0) != 0:
        fail(errors, "suppressed follow-up mismatches are present")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--replay-json", type=Path)
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
        check_replay(load_json(args.replay_json), errors)

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
        "ok": not errors,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
